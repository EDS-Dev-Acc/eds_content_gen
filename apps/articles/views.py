"""
Article Viewer API views.

Phase 10.5: Operator Console MVP - Article Viewer with 7 tabs.
Phase 14.1: Added throttle classes for rate limiting.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Throttling and permissions
from apps.core.throttling import ExportEndpointThrottle, BulkActionThrottle, BurstThrottle
from apps.core.permissions import DestructiveActionPermission

# Request ID propagation for Celery tasks
from apps.core.middleware import celery_request_id_headers

from .models import (
    Article,
    ArticleRawCapture,
    ArticleScoreBreakdown,
    ArticleLLMArtifact,
    ArticleImage,
    ExportJob,
)
from .serializers import (
    ArticleListSerializer,
    ArticleInfoSerializer,
    ArticleDetailSerializer,
    ArticleDetailLightSerializer,
    ArticleContentSerializer,
    ArticleRawCaptureTabSerializer,
    ArticleExtractedTextSerializer,
    ArticleScoresTabSerializer,
    ArticleScoreBreakdownSerializer,
    ArticleLLMArtifactsTabSerializer,
    ArticleLLMArtifactListSerializer,
    ArticleLLMArtifactDetailSerializer,
    ArticleImagesTabSerializer,
    ArticleImageSerializer,
    ArticleUsageSerializer,
    ExportJobListSerializer,
    ExportJobDetailSerializer,
    ExportJobCreateSerializer,
)


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Article Viewer API.
    
    Provides list and detail views for articles with tab-based data access.
    
    GET /api/articles/                    - List articles
    GET /api/articles/{id}/               - Article detail (light by default)
    GET /api/articles/{id}/?include_content=true - Full article with content
    GET /api/articles/{id}/content/       - On-demand content loading
    GET /api/articles/{id}/info/          - Tab 1: Basic info
    GET /api/articles/{id}/raw_capture/   - Tab 2: Raw capture
    GET /api/articles/{id}/extracted/     - Tab 3: Extracted text
    GET /api/articles/{id}/scores/        - Tab 4: Scores breakdown
    GET /api/articles/{id}/llm_artifacts/ - Tab 5: LLM artifacts
    GET /api/articles/{id}/images/        - Tab 6: Images
    GET /api/articles/{id}/usage/         - Tab 7: Usage/history
    POST /api/articles/{id}/reprocess/    - Trigger reprocessing
    POST /api/articles/{id}/mark-used/    - Mark as used in content
    POST /api/articles/{id}/mark-ignored/ - Mark as ignored (exclude from use)
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [BurstThrottle]
    queryset = Article.objects.select_related('source').order_by('-total_score', '-collected_at')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ArticleListSerializer
        elif self.action == 'retrieve':
            # Check include_content parameter
            include_content = self.request.query_params.get('include_content', 'false').lower()
            if include_content in ('true', '1', 'yes'):
                return ArticleDetailSerializer
            return ArticleDetailLightSerializer
        return ArticleDetailSerializer
    
    @action(detail=True, methods=['get'])
    def content(self, request, pk=None):
        """
        On-demand content loading endpoint.
        
        Returns heavy content fields separately to optimize initial page load.
        """
        article = self.get_object()
        data = {
            'id': article.id,
            'raw_html': article.raw_html or '',
            'raw_html_size': len(article.raw_html) if article.raw_html else 0,
            'extracted_text': article.extracted_text or '',
            'extracted_text_size': len(article.extracted_text) if article.extracted_text else 0,
            'translated_text': article.translated_text or '',
            'translated_text_size': len(article.translated_text) if article.translated_text else 0,
            'original_language': article.original_language or '',
            'is_translated': bool(article.translated_text and article.original_language != 'en'),
        }
        serializer = ArticleContentSerializer(data)
        return Response(serializer.data)
    
    def get_queryset(self):
        """
        Filter articles by various parameters.
        """
        from django.utils.dateparse import parse_datetime
        
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(processing_status=status_filter)
        
        # Filter by source
        source_id = self.request.query_params.get('source')
        if not source_id:
            source_id = self.request.query_params.get('source_id')  # Alias
        if source_id:
            queryset = queryset.filter(source_id=source_id)
        
        # Filter by quality category
        quality = self.request.query_params.get('quality')
        if quality == 'high':
            queryset = queryset.filter(total_score__gte=70)
        elif quality == 'medium':
            queryset = queryset.filter(total_score__gte=50, total_score__lt=70)
        elif quality == 'low':
            queryset = queryset.filter(total_score__gt=0, total_score__lt=50)
        elif quality == 'unscored':
            queryset = queryset.filter(total_score=0)
        
        # Score range filters
        score_gte = self.request.query_params.get('score_gte')
        if score_gte:
            queryset = queryset.filter(total_score__gte=int(score_gte))
        score_lte = self.request.query_params.get('score_lte')
        if score_lte:
            queryset = queryset.filter(total_score__lte=int(score_lte))
        
        # Filter by topic
        topic = self.request.query_params.get('topic')
        if topic:
            queryset = queryset.filter(primary_topic__icontains=topic)
        
        # Filter by region
        region = self.request.query_params.get('region')
        if region:
            queryset = queryset.filter(primary_region=region)
        
        # Filter by language
        language = self.request.query_params.get('language')
        if language:
            queryset = queryset.filter(original_language=language)
        
        # Filter by AI detection
        ai_detected = self.request.query_params.get('ai_detected')
        if ai_detected is not None:
            ai_bool = ai_detected.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(ai_content_detected=ai_bool)
        
        # Filter by used status
        used = self.request.query_params.get('used')
        if used is not None:
            used_bool = used.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(used_in_content=used_bool)
        
        # Filter by has_images
        has_images = self.request.query_params.get('has_images')
        if has_images is not None:
            if has_images.lower() in ('true', '1', 'yes'):
                queryset = queryset.filter(images_count__gt=0)
            else:
                queryset = queryset.filter(images_count=0)
        
        # Filter by has_citations
        has_citations = self.request.query_params.get('has_citations')
        if has_citations is not None:
            queryset = queryset.filter(has_citations=has_citations.lower() in ('true', '1', 'yes'))
        
        # Filter by has_statistics
        has_statistics = self.request.query_params.get('has_statistics')
        if has_statistics is not None:
            queryset = queryset.filter(has_data_statistics=has_statistics.lower() in ('true', '1', 'yes'))
        
        # Filter by LLM processing (has LLM artifacts)
        llm_touched = self.request.query_params.get('llm_touched')
        if llm_touched is not None:
            llm_bool = llm_touched.lower() in ('true', '1', 'yes')
            if llm_bool:
                # Has at least one LLM artifact
                queryset = queryset.filter(llm_artifacts__isnull=False).distinct()
            else:
                # Has no LLM artifacts
                queryset = queryset.filter(llm_artifacts__isnull=True)
        
        # Date range filters
        collected_after = self.request.query_params.get('collected_after')
        if collected_after:
            dt = parse_datetime(collected_after)
            if dt:
                queryset = queryset.filter(collected_at__gte=dt)
        
        collected_before = self.request.query_params.get('collected_before')
        if collected_before:
            dt = parse_datetime(collected_before)
            if dt:
                queryset = queryset.filter(collected_at__lte=dt)
        
        published_after = self.request.query_params.get('published_after')
        if published_after:
            dt = parse_datetime(published_after)
            if dt:
                queryset = queryset.filter(published_date__gte=dt)
        
        published_before = self.request.query_params.get('published_before')
        if published_before:
            dt = parse_datetime(published_before)
            if dt:
                queryset = queryset.filter(published_date__lte=dt)
        
        # Search by title/URL
        search = self.request.query_params.get('search')
        if not search:
            search = self.request.query_params.get('q')  # Alias
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(url__icontains=search)
            )
        
        # Ordering
        ordering = self.request.query_params.get('ordering', '-total_score')
        valid_orderings = ['total_score', '-total_score', 'collected_at', '-collected_at',
                          'published_date', '-published_date', 'title', '-title',
                          'word_count', '-word_count']
        if ordering in valid_orderings:
            # Secondary sort by collected_at for stability
            queryset = queryset.order_by(ordering, '-collected_at')
        else:
            queryset = queryset.order_by('-total_score', '-collected_at')
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """Get full article detail with all related data."""
        instance = self.get_object()
        serializer = ArticleDetailSerializer(instance)
        return Response(serializer.data)
    
    # ========================================================================
    # Action Endpoints
    # ========================================================================
    
    @action(detail=True, methods=['post'], url_path='reprocess')
    def reprocess(self, request, pk=None):
        """
        Trigger reprocessing of an article.
        
        Resets the processing status and re-queues for extraction/scoring.
        """
        article = self.get_object()
        
        # Reset processing status
        old_status = article.processing_status
        article.processing_status = 'collected'
        article.processing_error = ''
        article.save()
        
        # Try to queue the reprocessing task with request_id propagation
        try:
            from apps.articles.tasks import process_article
            headers = celery_request_id_headers()
            task = process_article.apply_async(
                args=[str(article.id)],
                headers=headers,
            )
            task_id = task.id
        except Exception as e:
            task_id = None
        
        return Response({
            'id': str(article.id),
            'previous_status': old_status,
            'new_status': 'collected',
            'task_id': task_id,
            'message': f"Article queued for reprocessing",
        })
    
    @action(detail=True, methods=['post'], url_path='mark-used')
    def mark_used(self, request, pk=None):
        """Mark an article as used in content."""
        article = self.get_object()
        article.used_in_content = True
        article.usage_count = (article.usage_count or 0) + 1
        article.save()
        
        return Response({
            'id': str(article.id),
            'used_in_content': True,
            'usage_count': article.usage_count,
            'message': 'Article marked as used',
        })
    
    @action(detail=True, methods=['post'], url_path='mark-ignored')
    def mark_ignored(self, request, pk=None):
        """Mark an article as ignored (exclude from future use)."""
        article = self.get_object()
        
        # Use processing_status to mark as ignored
        article.processing_status = 'ignored'
        article.save()
        
        return Response({
            'id': str(article.id),
            'processing_status': 'ignored',
            'message': 'Article marked as ignored',
        })
    
    # ========================================================================
    # Tab Endpoints
    # ========================================================================
    
    @action(detail=True, methods=['get'], url_path='info')
    def info(self, request, pk=None):
        """
        Tab 1: Article info - basic details and metadata.
        """
        article = self.get_object()
        serializer = ArticleInfoSerializer(article)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='raw_capture')
    def raw_capture(self, request, pk=None):
        """
        Tab 2: Raw capture - HTTP response, headers, raw HTML.
        """
        article = self.get_object()
        
        # Try to get the capture record
        try:
            capture = article.raw_capture
            data = {
                'has_capture_record': True,
                'http_status': capture.http_status,
                'response_headers': capture.response_headers,
                'request_headers': capture.request_headers,
                'fetch_method': capture.fetch_method,
                'fetch_duration_ms': capture.fetch_duration_ms,
                'fetched_at': capture.fetched_at,
                'content_type': capture.content_type,
                'content_length': capture.content_length,
                'final_url': capture.final_url,
                'raw_html': article.raw_html or '',
                'raw_html_length': len(article.raw_html) if article.raw_html else 0,
            }
        except ArticleRawCapture.DoesNotExist:
            # Fall back to just the raw HTML from Article
            data = {
                'has_capture_record': False,
                'http_status': None,
                'response_headers': {},
                'request_headers': {},
                'fetch_method': '',
                'fetch_duration_ms': None,
                'fetched_at': None,
                'content_type': '',
                'content_length': None,
                'final_url': '',
                'raw_html': article.raw_html or '',
                'raw_html_length': len(article.raw_html) if article.raw_html else 0,
            }
        
        serializer = ArticleRawCaptureTabSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='extracted')
    def extracted(self, request, pk=None):
        """
        Tab 3: Extracted text - cleaned content.
        """
        article = self.get_object()
        
        data = {
            'extracted_text': article.extracted_text or '',
            'translated_text': article.translated_text or '',
            'original_language': article.original_language or '',
            'is_translated': article.is_translated,
            'word_count': article.word_count,
            'extracted_text_length': len(article.extracted_text) if article.extracted_text else 0,
            'translated_text_length': len(article.translated_text) if article.translated_text else 0,
        }
        
        serializer = ArticleExtractedTextSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='scores')
    def scores(self, request, pk=None):
        """
        Tab 4: Scores breakdown with reasoning.
        """
        article = self.get_object()
        
        # Try to get detailed breakdown
        try:
            breakdown = article.score_breakdown
            breakdown_data = ArticleScoreBreakdownSerializer(breakdown).data
            has_breakdown = True
        except ArticleScoreBreakdown.DoesNotExist:
            breakdown_data = None
            has_breakdown = False
        
        data = {
            # Summary scores from Article
            'reputation_score': article.reputation_score,
            'recency_score': article.recency_score,
            'topic_alignment_score': article.topic_alignment_score,
            'content_quality_score': article.content_quality_score,
            'geographic_relevance_score': article.geographic_relevance_score,
            'ai_penalty': article.ai_penalty,
            'total_score': article.total_score,
            'quality_category': article.quality_category,
            
            # AI Detection
            'ai_content_detected': article.ai_content_detected,
            'ai_confidence_score': article.ai_confidence_score or 0.0,
            'ai_detection_reasoning': article.ai_detection_reasoning or '',
            
            # Breakdown
            'has_breakdown': has_breakdown,
            'breakdown': breakdown_data,
        }
        
        serializer = ArticleScoresTabSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='llm_artifacts')
    def llm_artifacts(self, request, pk=None):
        """
        Tab 5: LLM artifacts - prompt/response pairs.
        """
        article = self.get_object()
        artifacts = article.llm_artifacts.all()
        
        # Calculate aggregates
        aggregates = artifacts.aggregate(
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('estimated_cost')
        )
        
        # Get unique artifact types
        artifact_types = list(artifacts.values_list('artifact_type', flat=True).distinct())
        
        data = {
            'total_count': artifacts.count(),
            'total_tokens': aggregates['total_tokens'] or 0,
            'total_cost': aggregates['total_cost'] or Decimal('0'),
            'artifact_types': artifact_types,
            'artifacts': ArticleLLMArtifactListSerializer(artifacts, many=True).data,
        }
        
        serializer = ArticleLLMArtifactsTabSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='images')
    def images(self, request, pk=None):
        """
        Tab 6: Images - extracted images.
        """
        article = self.get_object()
        images = article.images.all()
        
        data = {
            'total_count': images.count(),
            'has_primary': images.filter(is_primary=True).exists(),
            'infographics_count': images.filter(is_infographic=True).count(),
            'images': ArticleImageSerializer(images, many=True).data,
        }
        
        serializer = ArticleImagesTabSerializer(data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='usage')
    def usage(self, request, pk=None):
        """
        Tab 7: Usage and history.
        """
        article = self.get_object()
        
        # Calculate days since collected
        from django.utils import timezone
        days_since_collected = 0
        if article.collected_at:
            delta = timezone.now() - article.collected_at
            days_since_collected = delta.days
        
        data = {
            'used_in_content': article.used_in_content,
            'usage_count': article.usage_count,
            
            # Timestamps
            'collected_at': article.collected_at,
            'created_at': article.created_at,
            'updated_at': article.updated_at,
            'published_date': article.published_date,
            
            # Processing history
            'processing_status': article.processing_status,
            'processing_error': article.processing_error or '',
            
            # Derived
            'age_days': article.age_days,
            'days_since_collected': days_since_collected,
            
            # Source info
            'source_id': article.source_id,
            'source_name': article.source.name if article.source else '',
            'source_crawl_frequency_hours': getattr(article.source, 'crawl_frequency_hours', None),
        }
        
        serializer = ArticleUsageSerializer(data)
        return Response(serializer.data)


class ArticleLLMArtifactDetailView(APIView):
    """
    Get full detail of a specific LLM artifact.
    
    GET /api/articles/llm_artifacts/{id}/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            artifact = ArticleLLMArtifact.objects.get(pk=pk)
        except ArticleLLMArtifact.DoesNotExist:
            return Response(
                {'error': 'LLM artifact not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ArticleLLMArtifactDetailSerializer(artifact)
        return Response(serializer.data)


class ArticleStatsView(APIView):
    """
    Get aggregate statistics for articles.
    
    GET /api/articles/stats/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from django.db.models import Avg, Max, Min
        
        # Get base queryset
        articles = Article.objects.all()
        
        # Overall counts
        total = articles.count()
        by_status = dict(
            articles.values('processing_status')
            .annotate(count=Count('id'))
            .values_list('processing_status', 'count')
        )
        
        # Quality breakdown
        high_quality = articles.filter(total_score__gte=70).count()
        medium_quality = articles.filter(total_score__gte=50, total_score__lt=70).count()
        low_quality = articles.filter(total_score__gt=0, total_score__lt=50).count()
        unscored = articles.filter(total_score=0).count()
        
        # AI detection
        ai_detected = articles.filter(ai_content_detected=True).count()
        
        # Usage
        used = articles.filter(used_in_content=True).count()
        
        # Score stats
        score_stats = articles.filter(total_score__gt=0).aggregate(
            avg_score=Avg('total_score'),
            max_score=Max('total_score'),
            min_score=Min('total_score'),
        )
        
        # Top topics
        top_topics = list(
            articles.exclude(primary_topic='')
            .values('primary_topic')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        # Top regions
        top_regions = list(
            articles.exclude(primary_region='')
            .values('primary_region')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        return Response({
            'total': total,
            'by_status': by_status,
            'quality': {
                'high': high_quality,
                'medium': medium_quality,
                'low': low_quality,
                'unscored': unscored,
            },
            'ai_detected': ai_detected,
            'used_in_content': used,
            'score_stats': {
                'average': round(score_stats['avg_score'] or 0, 2),
                'max': score_stats['max_score'] or 0,
                'min': score_stats['min_score'] or 0,
            },
            'top_topics': top_topics,
            'top_regions': top_regions,
        })


class ArticleBulkActionView(APIView):
    """
    Perform bulk actions on articles.
    
    POST /api/articles/bulk/
    
    Actions:
    - mark_used, mark_ignored, reprocess: require IsAuthenticated
    - delete: requires DestructiveActionPermission
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [BulkActionThrottle]
    
    def get_permissions(self):
        """Apply DestructiveActionPermission for delete action."""
        permissions = super().get_permissions()
        # Check if this is a delete action and add extra permission
        if self.request.method == 'POST':
            action = self.request.data.get('action')
            if action == 'delete':
                permissions.append(DestructiveActionPermission())
        return permissions
    
    def post(self, request):
        """Perform bulk action on articles."""
        article_ids = request.data.get('article_ids', [])
        action = request.data.get('action')
        
        if not article_ids:
            return Response(
                {'error': 'article_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if action not in ['mark_used', 'mark_ignored', 'reprocess', 'delete']:
            return Response(
                {'error': f"Invalid action: {action}. Valid: mark_used, mark_ignored, reprocess, delete"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = Article.objects.filter(id__in=article_ids)
        count = queryset.count()
        
        if action == 'mark_used':
            queryset.update(used_in_content=True)
            message = f"Marked {count} articles as used"
        elif action == 'mark_ignored':
            queryset.update(processing_status='ignored')
            message = f"Marked {count} articles as ignored"
        elif action == 'reprocess':
            queryset.update(processing_status='collected', processing_error='')
            # Try to queue reprocessing tasks
            try:
                from apps.articles.tasks import process_article_pipeline
                for article_id in article_ids:
                    process_article_pipeline.delay(str(article_id))
            except Exception:
                pass
            message = f"Queued {count} articles for reprocessing"
        elif action == 'delete':
            queryset.delete()
            message = f"Deleted {count} articles"
        
        return Response({
            'action': action,
            'count': count,
            'message': message,
        })


class ArticleExportView(APIView):
    """
    Export articles in various formats.
    
    GET /api/articles/export/?format=json&...filters...
    GET /api/articles/export/?format=csv&...filters...
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ExportEndpointThrottle]
    
    def get(self, request):
        """Export articles with optional filters."""
        import json
        import csv
        from io import StringIO
        from django.http import HttpResponse
        
        export_format = request.query_params.get('format', 'json')
        limit = min(int(request.query_params.get('limit', 1000)), 5000)  # Cap at 5000
        
        # Build queryset with filters (reuse ArticleViewSet logic)
        queryset = Article.objects.select_related('source').order_by('-total_score')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(processing_status=status_filter)
        
        source_id = request.query_params.get('source')
        if source_id:
            queryset = queryset.filter(source_id=source_id)
        
        quality = request.query_params.get('quality')
        if quality == 'high':
            queryset = queryset.filter(total_score__gte=70)
        elif quality == 'medium':
            queryset = queryset.filter(total_score__gte=50, total_score__lt=70)
        elif quality == 'low':
            queryset = queryset.filter(total_score__gt=0, total_score__lt=50)
        
        score_gte = request.query_params.get('score_gte')
        if score_gte:
            queryset = queryset.filter(total_score__gte=int(score_gte))
        
        topic = request.query_params.get('topic')
        if topic:
            queryset = queryset.filter(primary_topic__icontains=topic)
        
        region = request.query_params.get('region')
        if region:
            queryset = queryset.filter(primary_region=region)
        
        # Limit results
        articles = queryset[:limit]
        
        if export_format == 'csv':
            # Generate CSV
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'id', 'title', 'url', 'source_name', 'source_domain',
                'published_date', 'collected_at', 'total_score', 'quality_category',
                'primary_topic', 'primary_region', 'original_language',
                'word_count', 'ai_content_detected', 'used_in_content',
            ])
            
            # Data
            for article in articles:
                writer.writerow([
                    str(article.id),
                    article.title,
                    article.url,
                    article.source.name if article.source else '',
                    article.source.domain if article.source else '',
                    article.published_date.isoformat() if article.published_date else '',
                    article.collected_at.isoformat() if article.collected_at else '',
                    article.total_score,
                    article.quality_category,
                    article.primary_topic,
                    article.primary_region,
                    article.original_language,
                    article.word_count,
                    article.ai_content_detected,
                    article.used_in_content,
                ])
            
            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="articles_export.csv"'
            return response
        
        else:
            # JSON export
            data = []
            for article in articles:
                data.append({
                    'id': str(article.id),
                    'title': article.title,
                    'url': article.url,
                    'source': {
                        'id': str(article.source.id) if article.source else None,
                        'name': article.source.name if article.source else None,
                        'domain': article.source.domain if article.source else None,
                    },
                    'published_date': article.published_date.isoformat() if article.published_date else None,
                    'collected_at': article.collected_at.isoformat() if article.collected_at else None,
                    'total_score': article.total_score,
                    'quality_category': article.quality_category,
                    'primary_topic': article.primary_topic,
                    'primary_region': article.primary_region,
                    'original_language': article.original_language,
                    'word_count': article.word_count,
                    'ai_content_detected': article.ai_content_detected,
                    'used_in_content': article.used_in_content,
                    'extracted_text': article.extracted_text[:500] if article.extracted_text else '',
                })
            
            return Response({
                'count': len(data),
                'articles': data,
            })


class ExportJobViewSet(viewsets.ModelViewSet):
    """
    Async export job management.
    
    POST /api/exports/ - Create new export job
    GET /api/exports/ - List user's export jobs
    GET /api/exports/{id}/ - Get export job status
    GET /api/exports/{id}/download/ - Download completed export
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']
    
    def get_throttles(self):
        """Apply throttling to create action."""
        if self.action == 'create':
            return [ExportEndpointThrottle()]
        return []
    
    def get_queryset(self):
        """Users see only their exports unless admin."""
        queryset = ExportJob.objects.all().order_by('-created_at')
        if not self.request.user.is_superuser:
            queryset = queryset.filter(requested_by=self.request.user)
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ExportJobCreateSerializer
        elif self.action == 'retrieve':
            return ExportJobDetailSerializer
        return ExportJobListSerializer
    
    def create(self, request, *args, **kwargs):
        """Create and queue an export job."""
        from django.urls import reverse
        
        serializer = ExportJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Create export job
        export_job = ExportJob.objects.create(
            export_type=data.get('type', 'articles'),
            format=data.get('format', 'csv'),
            params=data.get('filter_params', {}),
            requested_by=request.user,
            status='queued',
        )
        
        # Queue Celery task
        try:
            from .tasks import generate_export
            generate_export.apply_async(
                args=[str(export_job.id)],
                headers=celery_request_id_headers(),
            )
        except Exception as e:
            # Mark as queued but note the error - may execute later
            export_job.error_message = f"Task queuing warning: {e}"
            export_job.save()
        
        # Build full URLs for status and download
        export_id = str(export_job.id)
        status_url = request.build_absolute_uri(f'/api/exports/{export_id}/')
        download_url = request.build_absolute_uri(f'/api/exports/{export_id}/download/')
        
        return Response({
            'export_id': export_id,
            'status': export_job.status,
            'status_url': status_url,
            'download_url': download_url,
            'message': 'Export job created and queued. Poll status_url for progress, then use download_url when completed.',
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download completed export file."""
        from django.http import FileResponse
        import os
        
        export_job = self.get_object()
        
        if export_job.status != 'completed':
            return Response(
                {'error': f"Export not ready. Status: {export_job.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not export_job.file_path or not os.path.exists(export_job.file_path):
            return Response(
                {'error': 'Export file not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Determine content type
        content_types = {
            'csv': 'text/csv',
            'json': 'application/json',
            'markdown_zip': 'application/zip',
        }
        content_type = content_types.get(export_job.format, 'application/octet-stream')
        
        # Filename
        ext = 'zip' if export_job.format == 'markdown_zip' else export_job.format
        filename = f"export_{export_job.id}.{ext}"
        
        return FileResponse(
            open(export_job.file_path, 'rb'),
            as_attachment=True,
            filename=filename,
            content_type=content_type,
        )
