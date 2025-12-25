"""
API endpoints for content opportunities and draft generation.

Phase 12 & 13: Comprehensive ViewSets for opportunities, drafts, templates.
"""

from django.db.models import Q
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny

from django_filters import rest_framework as filters

from apps.articles.models import Article
from .models import ContentOpportunity, OpportunityBatch, ContentDraft, DraftFeedback, SynthesisTemplate
from .serializers import (
    ArticleSummarySerializer,
    ArticleDetailForContentSerializer,
    # Opportunity serializers
    OpportunityRequestSerializer,
    ContentOpportunityListSerializer,
    ContentOpportunityDetailSerializer,
    ContentOpportunityUpdateSerializer,
    OpportunityBatchRequestSerializer,
    OpportunityBatchSerializer,
    OpportunityGenerationResponseSerializer,
    # Draft serializers
    DraftRequestSerializer,
    ContentDraftListSerializer,
    ContentDraftDetailSerializer,
    ContentDraftUpdateSerializer,
    DraftRegenerateSerializer,
    DraftRefineSerializer,
    DraftGenerationResponseSerializer,
    # Feedback serializers
    DraftFeedbackSerializer,
    DraftFeedbackCreateSerializer,
    # Template serializers
    SynthesisTemplateSerializer,
    SynthesisTemplateCreateSerializer,
    # Stats serializers
    TrendingTopicsSerializer,
    CoverageStatsSerializer,
)
from .opportunity import OpportunityFinder
from .synthesis import DraftGenerator


# =============================================================================
# Filters
# =============================================================================

class ContentOpportunityFilter(filters.FilterSet):
    """Filters for content opportunities."""
    opportunity_type = filters.CharFilter(field_name='opportunity_type')
    status = filters.CharFilter(field_name='status')
    priority = filters.NumberFilter(field_name='priority')
    priority__gte = filters.NumberFilter(field_name='priority', lookup_expr='gte')
    min_score = filters.NumberFilter(field_name='composite_score', lookup_expr='gte')
    topic = filters.CharFilter(field_name='primary_topic', lookup_expr='icontains')
    region = filters.CharFilter(field_name='primary_region', lookup_expr='icontains')
    detection_method = filters.CharFilter(field_name='detection_method')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    not_expired = filters.BooleanFilter(method='filter_not_expired')
    
    def filter_not_expired(self, queryset, name, value):
        if value:
            return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        return queryset
    
    class Meta:
        model = ContentOpportunity
        fields = ['opportunity_type', 'status', 'priority', 'primary_topic', 'primary_region']


class ContentDraftFilter(filters.FilterSet):
    """Filters for content drafts."""
    content_type = filters.CharFilter(field_name='content_type')
    voice = filters.CharFilter(field_name='voice')
    status = filters.CharFilter(field_name='status')
    min_quality = filters.NumberFilter(field_name='quality_score', lookup_expr='gte')
    min_originality = filters.NumberFilter(field_name='originality_score', lookup_expr='gte')
    min_words = filters.NumberFilter(field_name='word_count', lookup_expr='gte')
    max_words = filters.NumberFilter(field_name='word_count', lookup_expr='lte')
    generation_method = filters.CharFilter(field_name='generation_method')
    has_opportunity = filters.BooleanFilter(method='filter_has_opportunity')
    opportunity_id = filters.UUIDFilter(field_name='opportunity_id')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    def filter_has_opportunity(self, queryset, name, value):
        if value:
            return queryset.filter(opportunity__isnull=False)
        return queryset.filter(opportunity__isnull=True)
    
    class Meta:
        model = ContentDraft
        fields = ['content_type', 'voice', 'status']


# =============================================================================
# Opportunity Views
# =============================================================================

class OpportunityView(APIView):
    """
    Generate content opportunities on-the-fly.
    
    GET: Generate opportunities from recent articles (does not persist by default).
    """
    permission_classes = [AllowAny]  # TODO: Change to IsAuthenticated in production

    def get(self, request):
        serializer = OpportunityRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        data = OpportunityFinder().generate(
            limit=serializer.validated_data.get('limit', 10),
            topic=serializer.validated_data.get('topic', ''),
            region=serializer.validated_data.get('region', ''),
            min_score=serializer.validated_data.get('min_score', 0),
            max_age_days=serializer.validated_data.get('max_age_days', 7),
            include_gaps=serializer.validated_data.get('include_gaps', True),
            save=serializer.validated_data.get('save', False),
        )
        return Response(data, status=status.HTTP_200_OK)


class ContentOpportunityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing persisted content opportunities.
    
    Supports:
    - CRUD operations
    - Filtering by type, status, priority, topic, region
    - Actions: approve, reject, start-draft
    """
    queryset = ContentOpportunity.objects.all()
    permission_classes = [AllowAny]  # TODO: Change to IsAuthenticated
    filterset_class = ContentOpportunityFilter
    ordering_fields = ['composite_score', 'priority', 'created_at', 'expires_at']
    ordering = ['-composite_score', '-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContentOpportunityListSerializer
        elif self.action in ['update', 'partial_update']:
            return ContentOpportunityUpdateSerializer
        return ContentOpportunityDetailSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-composite_score')
        if ordering.lstrip('-') in self.ordering_fields:
            queryset = queryset.order_by(ordering)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = [self._serialize_opportunity(opp) for opp in page]
            return self.get_paginated_response(data)
        
        data = [self._serialize_opportunity(opp) for opp in queryset]
        return Response(data)
    
    def _serialize_opportunity(self, opp):
        return {
            'id': str(opp.id),
            'headline': opp.headline,
            'opportunity_type': opp.opportunity_type,
            'primary_topic': opp.primary_topic,
            'primary_region': opp.primary_region,
            'composite_score': opp.composite_score,
            'priority': opp.priority,
            'status': opp.status,
            'source_article_count': opp.source_article_count,
            'expires_at': opp.expires_at.isoformat() if opp.expires_at else None,
            'created_at': opp.created_at.isoformat(),
        }
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self._serialize_opportunity_detail(instance)
        return Response(data)
    
    def _serialize_opportunity_detail(self, opp):
        data = self._serialize_opportunity(opp)
        data.update({
            'angle': opp.angle,
            'summary': opp.summary,
            'secondary_topics': opp.secondary_topics,
            'secondary_regions': opp.secondary_regions,
            'confidence_score': opp.confidence_score,
            'relevance_score': opp.relevance_score,
            'timeliness_score': opp.timeliness_score,
            'detection_method': opp.detection_method,
            'detection_reasoning': opp.detection_reasoning,
            'llm_tokens_used': opp.llm_tokens_used,
            'updated_at': opp.updated_at.isoformat(),
            'source_articles': ArticleSummarySerializer(
                opp.source_articles.all(), many=True
            ).data,
        })
        return data
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = ContentOpportunityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        return Response(self._serialize_opportunity_detail(instance))
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an opportunity for content creation."""
        opp = self.get_object()
        opp.status = 'approved'
        opp.save()
        return Response({'status': 'approved', 'id': str(opp.id)})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an opportunity."""
        opp = self.get_object()
        opp.status = 'rejected'
        if request.data.get('reason'):
            opp.rejection_reason = request.data['reason']
        opp.save()
        return Response({'status': 'rejected', 'id': str(opp.id)})
    
    @action(detail=True, methods=['post'], url_path='start-draft')
    def start_draft(self, request, pk=None):
        """Generate a draft from this opportunity."""
        opp = self.get_object()
        
        # Get source article IDs
        article_ids = list(opp.source_articles.values_list('id', flat=True))
        
        # Generate draft
        result = DraftGenerator().generate(
            article_ids=[str(aid) for aid in article_ids],
            opportunity_id=str(opp.id),
            content_type=request.data.get('content_type', 'blog_post'),
            voice=request.data.get('voice', 'professional'),
            title_hint=opp.headline,
            focus_angle=opp.angle,
            save=True,
        )
        
        # Update opportunity status
        opp.status = 'in_progress'
        opp.save()
        
        return Response(result, status=status.HTTP_201_CREATED)


class OpportunityBatchView(APIView):
    """
    Trigger and check batch opportunity generation.
    
    POST: Start batch generation
    GET: Check batch status
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OpportunityBatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create batch record
        batch = OpportunityBatch.objects.create(
            status='pending',
            topic_filter=serializer.validated_data.get('topic_filter', ''),
            region_filter=serializer.validated_data.get('region_filter', ''),
            min_score=serializer.validated_data.get('min_score', 30),
            max_article_age_days=serializer.validated_data.get('max_article_age_days', 7),
            config=serializer.validated_data,
        )
        
        # Generate opportunities synchronously for now
        # TODO: Make async with Celery
        finder = OpportunityFinder()
        result = finder.generate(
            limit=serializer.validated_data.get('max_opportunities', 10) * 2,
            topic=batch.topic_filter,
            region=batch.region_filter,
            min_score=batch.min_score,
            max_age_days=batch.max_article_age_days,
            include_gaps=True,
            save=True,
        )
        
        batch.status = 'completed'
        batch.articles_analyzed = result.get('articles_analyzed', 0)
        batch.opportunities_found = len(result.get('opportunities', []))
        batch.completed_at = timezone.now()
        batch.save()
        
        return Response({
            'batch_id': str(batch.id),
            'status': batch.status,
            'opportunities_found': batch.opportunities_found,
        }, status=status.HTTP_201_CREATED)
    
    def get(self, request):
        batch_id = request.query_params.get('batch_id')
        if batch_id:
            try:
                batch = OpportunityBatch.objects.get(id=batch_id)
                return Response({
                    'id': str(batch.id),
                    'status': batch.status,
                    'topic_filter': batch.topic_filter,
                    'region_filter': batch.region_filter,
                    'articles_analyzed': batch.articles_analyzed,
                    'opportunities_found': batch.opportunities_found,
                    'started_at': batch.created_at.isoformat(),
                    'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
                })
            except OpportunityBatch.DoesNotExist:
                return Response({'error': 'Batch not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # List recent batches
        batches = OpportunityBatch.objects.order_by('-created_at')[:10]
        return Response({
            'results': [
                {
                    'id': str(b.id),
                    'status': b.status,
                    'opportunities_found': b.opportunities_found,
                    'created_at': b.created_at.isoformat(),
                }
                for b in batches
            ]
        })


class TrendingTopicsView(APIView):
    """Get trending topics from recent articles."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        days = int(request.query_params.get('days', 7))
        limit = int(request.query_params.get('limit', 10))
        
        topics = OpportunityFinder().get_trending_topics(days=days, limit=limit)
        return Response({'results': topics})


class CoverageStatsView(APIView):
    """Get coverage statistics for gap analysis."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        days = int(request.query_params.get('days', 7))
        stats = OpportunityFinder().get_coverage_stats(days=days)
        return Response(stats)


# =============================================================================
# Draft Views
# =============================================================================

class DraftView(APIView):
    """
    Generate content drafts on-the-fly.
    
    POST: Generate a draft from articles or opportunity.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = DraftGenerator().generate(
            article_ids=[str(aid) for aid in serializer.validated_data.get('article_ids', [])],
            opportunity_id=str(serializer.validated_data['opportunity_id']) if serializer.validated_data.get('opportunity_id') else None,
            content_type=serializer.validated_data.get('content_type', 'blog_post'),
            voice=serializer.validated_data.get('voice', 'analytical'),
            title_hint=serializer.validated_data.get('title_hint', ''),
            focus_angle=serializer.validated_data.get('focus_angle', ''),
            template_id=str(serializer.validated_data['template_id']) if serializer.validated_data.get('template_id') else None,
            save=serializer.validated_data.get('save', False),
        )
        return Response(data, status=status.HTTP_200_OK)


class ContentDraftViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing persisted content drafts.
    
    Supports:
    - CRUD operations
    - Filtering by type, status, quality scores
    - Actions: regenerate, refine, approve, publish
    """
    queryset = ContentDraft.objects.all()
    permission_classes = [AllowAny]  # TODO: Change to IsAuthenticated
    filterset_class = ContentDraftFilter
    ordering_fields = ['quality_score', 'originality_score', 'word_count', 'created_at', 'version']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContentDraftListSerializer
        elif self.action in ['update', 'partial_update']:
            return ContentDraftUpdateSerializer
        elif self.action == 'regenerate':
            return DraftRegenerateSerializer
        elif self.action == 'refine':
            return DraftRefineSerializer
        return ContentDraftDetailSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering.lstrip('-') in self.ordering_fields:
            queryset = queryset.order_by(ordering)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = [self._serialize_draft_list(d) for d in page]
            return self.get_paginated_response(data)
        
        data = [self._serialize_draft_list(d) for d in queryset]
        return Response(data)
    
    def _serialize_draft_list(self, draft):
        return {
            'id': str(draft.id),
            'title': draft.title,
            'content_type': draft.content_type,
            'voice': draft.voice,
            'word_count': draft.word_count,
            'quality_score': draft.quality_score,
            'originality_score': draft.originality_score,
            'version': draft.version,
            'status': draft.status,
            'source_article_count': draft.source_article_count,
            'created_at': draft.created_at.isoformat(),
        }
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self._serialize_draft_detail(instance)
        return Response(data)
    
    def _serialize_draft_detail(self, draft):
        data = self._serialize_draft_list(draft)
        data.update({
            'opportunity_id': str(draft.opportunity_id) if draft.opportunity_id else None,
            'parent_draft_id': str(draft.parent_draft_id) if draft.parent_draft_id else None,
            'subtitle': draft.subtitle,
            'excerpt': draft.excerpt,
            'content': draft.content,
            'content_html': draft.content_html,
            'content_hash': draft.content_hash,
            'published_at': draft.published_at.isoformat() if draft.published_at else None,
            'generation_method': draft.generation_method,
            'llm_tokens_used': draft.llm_tokens_used,
            'llm_cost': str(draft.llm_cost) if draft.llm_cost else None,
            'updated_at': draft.updated_at.isoformat(),
            'source_articles': ArticleSummarySerializer(
                draft.source_articles.all(), many=True
            ).data,
        })
        return data
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = ContentDraftUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        
        # Update word count if content changed
        if 'content' in serializer.validated_data:
            instance.word_count = len(instance.content.split())
        
        instance.save()
        return Response(self._serialize_draft_detail(instance))
    
    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """Regenerate draft with feedback."""
        draft = self.get_object()
        serializer = DraftRegenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = DraftGenerator().regenerate(
            draft_id=str(draft.id),
            feedback=serializer.validated_data.get('feedback', ''),
            preserve_sections=serializer.validated_data.get('preserve_sections'),
        )
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def refine(self, request, pk=None):
        """Refine a section of the draft."""
        draft = self.get_object()
        serializer = DraftRefineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = DraftGenerator().refine(
            draft_id=str(draft.id),
            section=serializer.validated_data.get('section', ''),
            instruction=serializer.validated_data.get('instruction', ''),
        )
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve draft for publication."""
        draft = self.get_object()
        draft.status = 'approved'
        draft.save()
        
        # Record feedback
        DraftFeedback.objects.create(
            draft=draft,
            feedback_type='approve',
            content=request.data.get('comment', 'Approved'),
            is_resolved=True,
            resolved_at=timezone.now(),
        )
        
        return Response({'status': 'approved', 'id': str(draft.id)})
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Mark draft as published."""
        draft = self.get_object()
        draft.status = 'published'
        draft.published_at = timezone.now()
        draft.save()
        
        # Update opportunity if linked
        if draft.opportunity:
            draft.opportunity.status = 'published'
            draft.opportunity.save()
        
        return Response({
            'status': 'published',
            'id': str(draft.id),
            'published_at': draft.published_at.isoformat(),
        })
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get all versions of a draft."""
        draft = self.get_object()
        
        # Find root draft
        root = draft
        while root.parent_draft:
            root = root.parent_draft
        
        # Get all versions
        versions = [root]
        children = list(ContentDraft.objects.filter(parent_draft=root).order_by('version'))
        versions.extend(children)
        
        # Recursively get grandchildren
        for child in children:
            grandchildren = list(ContentDraft.objects.filter(parent_draft=child).order_by('version'))
            versions.extend(grandchildren)
        
        return Response({
            'results': [self._serialize_draft_list(v) for v in versions]
        })
    
    @action(detail=True, methods=['get', 'post'])
    def feedback(self, request, pk=None):
        """Get or add feedback for a draft."""
        draft = self.get_object()
        
        if request.method == 'GET':
            feedbacks = DraftFeedback.objects.filter(draft=draft).order_by('-created_at')
            return Response({
                'results': [
                    {
                        'id': str(f.id),
                        'feedback_type': f.feedback_type,
                        'content': f.content,
                        'section': f.section,
                        'is_resolved': f.is_resolved,
                        'created_at': f.created_at.isoformat(),
                    }
                    for f in feedbacks
                ]
            })
        
        # POST - add feedback
        serializer = DraftFeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        feedback = DraftFeedback.objects.create(
            draft=draft,
            **serializer.validated_data
        )
        
        return Response({
            'id': str(feedback.id),
            'feedback_type': feedback.feedback_type,
            'content': feedback.content,
            'created_at': feedback.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


# =============================================================================
# Template Views
# =============================================================================

class SynthesisTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing synthesis templates.
    """
    queryset = SynthesisTemplate.objects.filter(is_active=True)
    permission_classes = [AllowAny]  # TODO: Change to IsAuthenticated
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SynthesisTemplateCreateSerializer
        return SynthesisTemplateSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        content_type = request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        return Response({
            'results': [
                {
                    'id': str(t.id),
                    'name': t.name,
                    'description': t.description,
                    'content_type': t.content_type,
                    'target_word_count': t.target_word_count,
                    'is_active': t.is_active,
                    'created_at': t.created_at.isoformat(),
                }
                for t in queryset
            ]
        })
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response({
            'id': str(instance.id),
            'name': instance.name,
            'description': instance.description,
            'prompt_template': instance.prompt_template,
            'system_prompt': instance.system_prompt,
            'content_type': instance.content_type,
            'target_word_count': instance.target_word_count,
            'max_tokens': instance.max_tokens,
            'is_active': instance.is_active,
            'created_at': instance.created_at.isoformat(),
            'updated_at': instance.updated_at.isoformat(),
        })
    
    def create(self, request, *args, **kwargs):
        serializer = SynthesisTemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        template = SynthesisTemplate.objects.create(**serializer.validated_data)
        return Response({
            'id': str(template.id),
            'name': template.name,
            'created_at': template.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = SynthesisTemplateCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        return Response({
            'id': str(instance.id),
            'name': instance.name,
            'updated_at': instance.updated_at.isoformat(),
        })


# =============================================================================
# Article Views (for content context)
# =============================================================================

class TopArticlesView(APIView):
    """Get top articles for content generation."""
    permission_classes = [AllowAny]

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        topic = request.query_params.get('topic')
        region = request.query_params.get('region')
        days = int(request.query_params.get('days', 7))
        
        cutoff = timezone.now() - timezone.timedelta(days=days)
        
        qs = Article.objects.filter(
            processing_status__in=["completed", "scored", "translated"],
            collected_at__gte=cutoff,
        )
        
        if topic:
            qs = qs.filter(primary_topic__icontains=topic)
        if region:
            qs = qs.filter(primary_region=region)
        
        qs = qs.order_by("-total_score", "-collected_at")[:limit]
        payload = ArticleSummarySerializer(qs, many=True).data
        return Response({"results": payload}, status=status.HTTP_200_OK)
