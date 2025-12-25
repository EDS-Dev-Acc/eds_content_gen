"""
API Views for Seeds app.

Phase 10.4: Seed CRUD, import, validate, and promote endpoints.
Phase 14: Enhanced with metrics instrumentation.
Phase 14.1: Added throttle classes for rate limiting.
"""

import logging
import uuid
from urllib.parse import urlparse

from django.utils import timezone
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Seed, SeedBatch
from .serializers import (
    SeedListSerializer,
    SeedDetailSerializer,
    SeedCreateSerializer,
    SeedUpdateSerializer,
    SeedBulkImportSerializer,
    SeedValidateSerializer,
    SeedPromoteSerializer,
    SeedBatchPromoteSerializer,
    SeedBatchSerializer,
    SeedRejectSerializer,
)

# Metrics - import at module level for performance
from apps.core.metrics import (
    increment_seeds_import,
    increment_seeds_discover,
    increment_test_crawl,
    observe_validation_duration,
)

# Throttling
from apps.core.throttling import (
    ImportEndpointThrottle,
    ProbeEndpointThrottle,
    DiscoveryEndpointThrottle,
    StateChangeThrottle,
    BulkActionThrottle,
    DestructiveActionThrottle,
)

from django.conf import settings

logger = logging.getLogger(__name__)


class SeedPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class SeedViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing seeds.
    
    GET /api/seeds/ - List all seeds
    POST /api/seeds/ - Create a seed
    GET /api/seeds/{id}/ - Get seed details
    PUT /api/seeds/{id}/ - Update a seed
    DELETE /api/seeds/{id}/ - Delete a seed
    """
    permission_classes = [IsAuthenticated]
    pagination_class = SeedPagination
    
    def get_throttles(self):
        """Apply throttling to destructive actions."""
        if self.action == 'destroy':
            return [DestructiveActionThrottle()]
        return []
    
    def get_queryset(self):
        """Get seeds with optional filtering."""
        queryset = Seed.objects.select_related(
            'added_by', 'promoted_to', 'promoted_by',
            'discovered_from_source', 'discovered_from_run'
        )
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by domain
        domain = self.request.query_params.get('domain')
        if domain:
            queryset = queryset.filter(domain__icontains=domain)
        
        # Filter by promotable
        promotable = self.request.query_params.get('promotable')
        if promotable and promotable.lower() == 'true':
            queryset = queryset.filter(
                status='valid',
                is_reachable=True,
                is_crawlable=True,
                promoted_to__isnull=True
            )
        
        # Filter by batch
        batch_id = self.request.query_params.get('batch')
        if batch_id:
            queryset = queryset.filter(import_batch_id=batch_id)
        
        # Filter by tag
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        
        # Filter by seed_type
        seed_type = self.request.query_params.get('seed_type') or self.request.query_params.get('type')
        if seed_type:
            queryset = queryset.filter(seed_type=seed_type)
        
        # Filter by country
        country = self.request.query_params.get('country')
        if country:
            queryset = queryset.filter(country=country.upper())
        
        # Filter by region (check in regions JSON array)
        region = self.request.query_params.get('region')
        if region:
            queryset = queryset.filter(regions__contains=[region])
        
        # Filter by topic (check in topics JSON array)
        topic = self.request.query_params.get('topic')
        if topic:
            queryset = queryset.filter(topics__contains=[topic])
        
        # Filter by discovered_from_source
        discovered_from = self.request.query_params.get('discovered_from_source_id')
        if discovered_from:
            queryset = queryset.filter(discovered_from_source_id=discovered_from)
        
        # Filter by date range
        created_after = self.request.query_params.get('created_at_after') or self.request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        created_before = self.request.query_params.get('created_at_before') or self.request.query_params.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        # Filter by confidence range
        min_confidence = self.request.query_params.get('confidence_gte')
        if min_confidence:
            queryset = queryset.filter(confidence__gte=int(min_confidence))
        
        max_confidence = self.request.query_params.get('confidence_lte')
        if max_confidence:
            queryset = queryset.filter(confidence__lte=int(max_confidence))
        
        # Search (q as alias for search)
        search = self.request.query_params.get('search') or self.request.query_params.get('q')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(url__icontains=search) | 
                Q(domain__icontains=search) |
                Q(notes__icontains=search)
            )
        
        # Ordering
        ordering = self.request.query_params.get('ordering', '-created_at')
        allowed_orderings = [
            'created_at', '-created_at',
            'updated_at', '-updated_at',
            'validated_at', '-validated_at',
            'domain', '-domain',
            'confidence', '-confidence',
            'status', '-status',
        ]
        if ordering in allowed_orderings:
            return queryset.order_by(ordering)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'retrieve':
            return SeedDetailSerializer
        elif self.action == 'create':
            return SeedCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return SeedUpdateSerializer
        return SeedListSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a seed and return full detail."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        # Return detail serializer for full response
        detail_serializer = SeedDetailSerializer(instance)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    def perform_destroy(self, instance):
        """Log seed deletion."""
        logger.info(f"Deleted seed: {instance.url}")
        instance.delete()


class SeedBulkImportView(APIView):
    """
    Bulk import seeds from a list of URLs.
    
    POST /api/seeds/import/
    
    Request body:
        urls: List of URLs to import (for 'urls' format)
        text: Text containing URLs (for 'text'/'csv' format)
        format: 'urls', 'text', or 'csv'
        tags: Tags to apply to all imported seeds
        skip_duplicates: If true (default), skip duplicates silently
        on_duplicate: Strategy for handling duplicates - 'skip' (default), 
                      'update', or 'error'
    
    Uses normalized_url for duplicate detection to catch equivalent URLs
    (e.g., trailing slashes, port 80/443, etc.)
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ImportEndpointThrottle]
    
    def post(self, request):
        """Import multiple seeds at once."""
        from apps.core.security import URLNormalizer
        
        serializer = SeedBulkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        urls = serializer.extract_urls(data)
        tags = data.get('tags', [])
        
        # Support both skip_duplicates (legacy) and on_duplicate (new)
        on_duplicate = data.get('on_duplicate', 'skip')
        if not data.get('skip_duplicates', True):
            on_duplicate = 'error'  # Legacy compatibility
        
        # Get update_fields for selective updates
        update_fields = data.get('update_fields', [])
        # If no update_fields specified, default to tags only for backwards compatibility
        if not update_fields and on_duplicate == 'update':
            update_fields = ['tags']
        
        # Create batch record
        batch = SeedBatch.objects.create(
            name=f"Import {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            import_source=data.get('format', 'urls'),
            total_count=len(urls),
            imported_by=request.user,
        )
        
        created = []
        updated = []
        duplicates = []
        errors = []
        
        with transaction.atomic():
            for url in urls:
                try:
                    # Normalize URL for duplicate detection
                    try:
                        normalized = URLNormalizer.normalize(url)
                    except Exception:
                        normalized = url
                    
                    # Check for duplicate using normalized_url
                    existing = Seed.objects.filter(
                        normalized_url=normalized
                    ).exclude(status='promoted').first()
                    
                    if existing:
                        if on_duplicate == 'skip':
                            duplicates.append({
                                'url': url,
                                'normalized_url': normalized,
                                'existing_id': str(existing.id),
                                'action': 'skipped',
                            })
                            continue
                        elif on_duplicate == 'update':
                            # Track merged fields with before/after values
                            merged_fields = {}
                            
                            # Merge tags: union unique, preserve order (existing first)
                            if 'tags' in update_fields and tags:
                                before_tags = list(existing.tags or [])
                                # Union while preserving order
                                new_tags = list(dict.fromkeys(before_tags + tags))
                                if new_tags != before_tags:
                                    merged_fields['tags'] = {
                                        'before': before_tags,
                                        'after': new_tags,
                                    }
                                    existing.tags = new_tags
                            
                            # Merge notes: append with timestamp
                            if 'notes' in update_fields and data.get('notes'):
                                before_notes = existing.notes or ''
                                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                                new_notes = f"{before_notes}\n[Import merge {timestamp}]: {data['notes']}".strip()
                                merged_fields['notes'] = {
                                    'before': before_notes,
                                    'after': new_notes,
                                }
                                existing.notes = new_notes
                            
                            # Update confidence if provided
                            if 'confidence' in update_fields and data.get('confidence') is not None:
                                before_conf = existing.confidence
                                existing.confidence = data['confidence']
                                merged_fields['confidence'] = {
                                    'before': before_conf,
                                    'after': existing.confidence,
                                }
                            
                            # Update seed_type if provided
                            if 'seed_type' in update_fields and data.get('seed_type'):
                                before_type = existing.seed_type
                                existing.seed_type = data['seed_type']
                                merged_fields['seed_type'] = {
                                    'before': before_type,
                                    'after': existing.seed_type,
                                }
                            
                            # Update country if provided
                            if 'country' in update_fields and data.get('country'):
                                before_country = existing.country
                                existing.country = data['country']
                                merged_fields['country'] = {
                                    'before': before_country,
                                    'after': existing.country,
                                }
                            
                            # Merge regions: union unique
                            if 'regions' in update_fields and data.get('regions'):
                                before_regions = list(existing.regions or [])
                                new_regions = list(dict.fromkeys(before_regions + data['regions']))
                                if new_regions != before_regions:
                                    merged_fields['regions'] = {
                                        'before': before_regions,
                                        'after': new_regions,
                                    }
                                    existing.regions = new_regions
                            
                            # Merge topics: union unique
                            if 'topics' in update_fields and data.get('topics'):
                                before_topics = list(existing.topics or [])
                                new_topics = list(dict.fromkeys(before_topics + data['topics']))
                                if new_topics != before_topics:
                                    merged_fields['topics'] = {
                                        'before': before_topics,
                                        'after': new_topics,
                                    }
                                    existing.topics = new_topics
                            
                            existing.import_batch_id = batch.id
                            existing.save()
                            
                            updated.append({
                                'id': str(existing.id),
                                'url': existing.url,
                                'normalized_url': normalized,
                                'domain': existing.domain,
                                'action': 'updated',
                                'merged_fields': merged_fields,
                            })
                            continue
                        else:  # 'error'
                            errors.append({
                                'url': url,
                                'normalized_url': normalized,
                                'error': 'Duplicate URL',
                                'existing_id': str(existing.id),
                            })
                            continue
                    
                    # Create seed (normalized_url auto-populated on save)
                    seed = Seed.objects.create(
                        url=url,
                        tags=tags,
                        import_source=data.get('format', 'api'),
                        import_batch_id=batch.id,
                        added_by=request.user,
                    )
                    created.append({
                        'id': str(seed.id),
                        'url': seed.url,
                        'normalized_url': seed.normalized_url,
                        'domain': seed.domain,
                    })
                    
                except Exception as e:
                    errors.append({
                        'url': url,
                        'error': str(e)
                    })
        
        # Update batch stats
        batch.success_count = len(created) + len(updated)
        batch.duplicate_count = len(duplicates)
        batch.error_count = len(errors)
        batch.errors = errors
        batch.save()
        
        logger.info(
            f"Bulk import: {len(created)} created, {len(updated)} updated, "
            f"{len(duplicates)} duplicates, {len(errors)} errors"
        )
        
        # Record metrics
        import_format = data.get('format', 'urls')
        if len(created) > 0 or len(updated) > 0:
            increment_seeds_import(count=len(created) + len(updated), status='success', format=import_format)
        if len(errors) > 0:
            increment_seeds_import(count=len(errors), status='error', format=import_format)
        
        return Response({
            'batch_id': str(batch.id),
            'total': len(urls),
            'created': len(created),
            'updated': len(updated),
            'duplicates': len(duplicates),
            'errors': len(errors),
            'created_seeds': created[:10],  # First 10 for preview
            'updated_seeds': updated[:10],
            'duplicates_detail': duplicates[:20],  # Show more for diagnostics
            'error_details': errors[:10],
        }, status=status.HTTP_201_CREATED)


class SeedValidateView(APIView):
    """
    Validate a seed URL.
    
    POST /api/seeds/{id}/validate/
    
    Enhanced response includes:
        - final_url: The URL after following redirects
        - content_type: Detected MIME type
        - warnings: Non-fatal issues (robots restrictions, redirects, etc.)
        - detected.type_hint: Suggested source type (news, blog, rss, sitemap)
        - detected.feed_urls: Discovered RSS/Atom feed URLs
        - detected.sitemap_url: Discovered sitemap URL
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProbeEndpointThrottle]
    
    def post(self, request, pk):
        """Validate a seed URL."""
        from apps.core.security import SafeHTTPClient, SSRFError
        from apps.core.exceptions import ErrorCode
        import re
        
        try:
            seed = Seed.objects.get(pk=pk)
        except Seed.DoesNotExist:
            return Response(
                {'error': {'code': ErrorCode.NOT_FOUND.value, 'message': 'Seed not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if seed.status == 'promoted':
            return Response(
                {'error': {'code': ErrorCode.VALIDATION_ERROR.value, 'message': 'Cannot validate promoted seed'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status to validating
        seed.status = 'validating'
        seed.save()
        
        validation_errors = []
        warnings = []  # Non-fatal issues
        is_reachable = False
        is_crawlable = False
        has_articles = False
        article_count = 0
        
        # Enhanced detection fields
        final_url = None
        content_type = None
        type_hint = None
        detected_feeds = []
        sitemap_url = None
        
        # Use safe HTTP client with SSRF protection
        client = SafeHTTPClient(
            timeout=(5, 15),
            max_retries=2,
        )
        
        try:
            # Check if URL is reachable (with SSRF protection)
            try:
                # Use GET instead of HEAD to capture redirect info
                response = client.get(seed.url, allow_redirects=True)
                is_reachable = response.status_code < 400
                
                # Capture final URL after redirects
                final_url = str(response.url)
                if final_url != seed.url:
                    warnings.append(f"URL redirects to: {final_url}")
                
                # Capture content type
                content_type = response.headers.get('content-type', '').split(';')[0].strip()
                
                if not is_reachable:
                    validation_errors.append(
                        f"URL returned status {response.status_code}"
                    )
            except SSRFError as e:
                validation_errors.append(f"Security: {str(e)}")
                seed.status = 'invalid'
                seed.validation_errors = validation_errors
                seed.validated_at = timezone.now()
                seed.save()
                return Response({
                    'id': str(seed.id),
                    'status': seed.status,
                    'errors': validation_errors,
                    'warnings': [],
                    'error': {'code': ErrorCode.SSRF_BLOCKED.value, 'message': str(e)},
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                validation_errors.append(f"Connection error: {str(e)}")
            
            # Check robots.txt
            robots_unknown = False  # Track if robots.txt status is uncertain
            if is_reachable:
                parsed = urlparse(final_url or seed.url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                robots_url = f"{base_url}/robots.txt"
                try:
                    from urllib.robotparser import RobotFileParser
                    rp = RobotFileParser()
                    rp.set_url(robots_url)
                    # Use safe fetch for robots.txt
                    try:
                        robots_response = client.get(robots_url, validate_content_type=False)
                        rp.parse(robots_response.text.splitlines())
                        is_crawlable = rp.can_fetch('*', seed.url)
                    except Exception as e:
                        # robots.txt fetch failed - add warning and mark unknown
                        warnings.append(f"robots.txt fetch failed ({str(e)[:50]}); assuming crawlable")
                        robots_unknown = True
                        is_crawlable = True  # Default to crawlable but flag as uncertain
                    
                    if not is_crawlable:
                        # This is a warning, not an error - site is still reachable
                        warnings.append("robots.txt restricts crawling for this URL")
                except Exception as e:
                    # Parser error - add warning and mark unknown
                    warnings.append(f"robots.txt parse error ({str(e)[:50]}); assuming crawlable")
                    robots_unknown = True
                    is_crawlable = True
            
            # Analyze content and detect type
            if is_reachable and response:
                try:
                    content = response.text
                    content_lower = content.lower()
                    
                    # Detect content type hint
                    if 'application/rss+xml' in content_type or 'application/atom+xml' in content_type:
                        type_hint = 'rss'
                    elif 'application/xml' in content_type or 'text/xml' in content_type:
                        if '<rss' in content_lower or '<feed' in content_lower:
                            type_hint = 'rss'
                        elif '<urlset' in content_lower or '<sitemapindex' in content_lower:
                            type_hint = 'sitemap'
                        else:
                            type_hint = 'xml'
                    elif 'text/html' in content_type:
                        # Analyze HTML for type hints
                        if any(term in content_lower for term in ['blog', 'wordpress', 'blogger']):
                            type_hint = 'blog'
                        elif any(term in content_lower for term in ['news', 'article', 'headline', 'breaking']):
                            type_hint = 'news'
                        else:
                            type_hint = 'website'
                    
                    # Look for RSS/Atom feed links
                    feed_patterns = [
                        r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\']',
                    ]
                    for pattern in feed_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            feed_url = match
                            if feed_url.startswith('/'):
                                feed_url = f"{base_url}{feed_url}"
                            if feed_url not in detected_feeds:
                                detected_feeds.append(feed_url)
                    
                    # Check common feed locations
                    if not detected_feeds:
                        common_feeds = ['/feed', '/rss', '/rss.xml', '/feed.xml', '/atom.xml']
                        for feed_path in common_feeds[:3]:  # Check first 3
                            try:
                                feed_check = client.head(f"{base_url}{feed_path}")
                                if feed_check.status_code == 200:
                                    detected_feeds.append(f"{base_url}{feed_path}")
                                    break
                            except Exception:
                                pass
                    
                    # Check for sitemap
                    try:
                        sitemap_check = client.head(f"{base_url}/sitemap.xml")
                        if sitemap_check.status_code == 200:
                            sitemap_url = f"{base_url}/sitemap.xml"
                    except Exception:
                        pass
                    
                    # Simple heuristic: look for article-like patterns
                    article_indicators = [
                        '<article', 'class="article"', 'class="post"',
                        'class="entry"', 'class="news"', '<h2', '<h3',
                    ]
                    indicator_count = sum(
                        1 for i in article_indicators if i in content_lower
                    )
                    
                    has_articles = indicator_count >= 2
                    
                    # Estimate article count from links
                    links = re.findall(r'href=["\']([^"\']+)["\']', content)
                    article_links = [
                        l for l in links 
                        if any(p in l for p in ['/article', '/news', '/post', '/blog', '/story'])
                    ]
                    article_count = len(set(article_links))
                    
                    if not has_articles:
                        warnings.append(
                            "No clear article structure detected on main page"
                        )
                        
                except Exception as e:
                    validation_errors.append(f"Content analysis error: {str(e)}")
        
        except Exception as e:
            validation_errors.append(f"Validation error: {str(e)}")
        finally:
            client.close()
        
        # Update seed with results
        seed.is_reachable = is_reachable
        seed.is_crawlable = is_crawlable
        seed.robots_unknown = robots_unknown
        seed.has_articles = has_articles
        seed.article_count_estimate = article_count if article_count > 0 else None
        seed.validation_errors = validation_errors
        seed.validated_at = timezone.now()
        
        # Set status based on results
        if is_reachable and is_crawlable:
            seed.status = 'valid'
        else:
            seed.status = 'invalid'
        
        seed.save()
        
        logger.info(f"Validated seed {seed.id}: {seed.status}")
        
        return Response({
            'id': str(seed.id),
            'status': seed.status,
            'is_reachable': is_reachable,
            'is_crawlable': is_crawlable,
            'robots_unknown': robots_unknown,  # True if robots.txt could not be fetched/parsed
            'has_articles': has_articles,
            'article_count_estimate': article_count,
            'errors': validation_errors,
            'warnings': warnings,
            'is_promotable': seed.is_promotable,
            # Enhanced fields
            'final_url': final_url,
            'content_type': content_type,
            'detected': {
                'type_hint': type_hint,
                'feed_urls': detected_feeds,
                'sitemap_url': sitemap_url,
            },
            'message': f"Seed validation complete: {seed.status}",
        })


class SeedPromoteView(APIView):
    """
    Promote a seed to a source.
    
    POST /api/seeds/{id}/promote/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [StateChangeThrottle]
    
    def post(self, request, pk):
        """Promote a seed to become a source."""
        from apps.sources.models import Source
        
        try:
            seed = Seed.objects.get(pk=pk)
        except Seed.DoesNotExist:
            return Response(
                {'error': 'Seed not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if seed.status == 'promoted':
            return Response(
                {'error': 'Seed already promoted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SeedPromoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Check if source with same domain exists
        existing = Source.objects.filter(domain=seed.domain).first()
        if existing:
            return Response({
                'error': f'Source already exists for domain {seed.domain}',
                'existing_source_id': str(existing.id),
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create source - map source_type to valid choices
            source_type_map = {
                'news': 'news_site',
                'blog': 'blog',
                'journal': 'research',
                'magazine': 'industry',
                'other': 'other',
            }
            mapped_type = source_type_map.get(data.get('source_type', 'news'), 'news_site')
            
            # Map crawl_frequency to hours
            freq_map = {'hourly': 1, 'daily': 24, 'weekly': 168}
            crawl_hours = freq_map.get(data.get('crawl_frequency', 'daily'), 24)
            
            # reputation_score is 0-100 integer, convert from 0-1 float
            rep_score = int(data.get('reputation_score', 0.5) * 100)
            
            source = Source.objects.create(
                name=data['name'],
                url=seed.url,
                domain=seed.domain,
                source_type=mapped_type,
                status='active' if data.get('auto_activate') else 'inactive',
                reputation_score=rep_score,
                crawl_frequency_hours=crawl_hours,
                crawler_config={
                    'max_articles_per_crawl': data.get('max_articles_per_crawl', 50),
                },
            )
            
            # Update seed
            seed.status = 'promoted'
            seed.promoted_to = source
            seed.promoted_at = timezone.now()
            seed.promoted_by = request.user
            seed.save()
        
        logger.info(f"Promoted seed {seed.id} to source {source.id}")
        
        return Response({
            'seed_id': str(seed.id),
            'source_id': str(source.id),
            'source_name': source.name,
            'source_status': source.status,
        }, status=status.HTTP_201_CREATED)


class SeedBatchPromoteView(APIView):
    """
    Batch promote multiple seeds to sources.
    
    POST /api/seeds/promote-batch/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [BulkActionThrottle]
    
    def post(self, request):
        """Promote multiple seeds at once."""
        from apps.sources.models import Source
        
        serializer = SeedBatchPromoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        seed_ids = data['seed_ids']
        
        seeds = Seed.objects.filter(id__in=seed_ids)
        
        promoted = []
        failed = []
        
        for seed in seeds:
            # Check if promotable
            if seed.status == 'promoted':
                failed.append({
                    'seed_id': str(seed.id),
                    'error': 'Already promoted'
                })
                continue
            
            if not seed.is_promotable:
                failed.append({
                    'seed_id': str(seed.id),
                    'error': 'Not promotable (validation failed or incomplete)'
                })
                continue
            
            # Check for existing source
            existing = Source.objects.filter(domain=seed.domain).first()
            if existing:
                failed.append({
                    'seed_id': str(seed.id),
                    'error': f'Source already exists for {seed.domain}'
                })
                continue
            
            try:
                with transaction.atomic():
                    # Map source_type to valid choices
                    source_type_map = {
                        'news': 'news_site',
                        'blog': 'blog',
                        'journal': 'research',
                        'magazine': 'industry',
                        'other': 'other',
                    }
                    mapped_type = source_type_map.get(data.get('source_type', 'news'), 'news_site')
                    
                    # Map crawl_frequency to hours
                    freq_map = {'hourly': 1, 'daily': 24, 'weekly': 168}
                    crawl_hours = freq_map.get(data.get('crawl_frequency', 'daily'), 24)
                    
                    # Create source
                    source = Source.objects.create(
                        name=seed.domain,
                        url=seed.url,
                        domain=seed.domain,
                        source_type=mapped_type,
                        status='active' if data.get('auto_activate') else 'inactive',
                        reputation_score=50,
                        crawl_frequency_hours=crawl_hours,
                    )
                    
                    # Update seed
                    seed.status = 'promoted'
                    seed.promoted_to = source
                    seed.promoted_at = timezone.now()
                    seed.promoted_by = request.user
                    seed.save()
                    
                    promoted.append({
                        'seed_id': str(seed.id),
                        'source_id': str(source.id),
                        'source_name': source.name,
                    })
            except Exception as e:
                failed.append({
                    'seed_id': str(seed.id),
                    'error': str(e)
                })
        
        logger.info(f"Batch promote: {len(promoted)} promoted, {len(failed)} failed")
        
        return Response({
            'promoted_count': len(promoted),
            'failed_count': len(failed),
            'promoted': promoted,
            'failed': failed,
        })


class SeedRejectView(APIView):
    """
    Reject a seed (mark as rejected).
    
    POST /api/seeds/{id}/reject/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Reject a seed."""
        try:
            seed = Seed.objects.get(pk=pk)
        except Seed.DoesNotExist:
            return Response(
                {'error': 'Seed not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if seed.status == 'promoted':
            return Response(
                {'error': 'Cannot reject promoted seed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SeedRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reason = serializer.validated_data.get('reason', '')
        
        seed.status = 'rejected'
        if reason:
            seed.notes = f"{seed.notes}\nRejected: {reason}".strip()
        seed.save()
        
        logger.info(f"Rejected seed {seed.id}")
        
        return Response({
            'id': str(seed.id),
            'status': 'rejected',
        })


class SeedBatchListView(APIView):
    """
    List seed import batches.
    
    GET /api/seeds/batches/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all import batches."""
        batches = SeedBatch.objects.select_related('imported_by').order_by('-created_at')
        
        paginator = PageNumberPagination()
        paginator.page_size = 25
        page = paginator.paginate_queryset(batches, request)
        
        serializer = SeedBatchSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SeedBatchDetailView(APIView):
    """
    Get seed batch details.
    
    GET /api/seeds/batches/{id}/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get batch details."""
        try:
            batch = SeedBatch.objects.get(pk=pk)
        except SeedBatch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SeedBatchSerializer(batch)
        
        # Include seeds from this batch
        seeds = Seed.objects.filter(import_batch_id=batch.id)
        seed_serializer = SeedListSerializer(seeds[:50], many=True)
        
        data = serializer.data
        data['seeds'] = seed_serializer.data
        data['seeds_count'] = seeds.count()
        
        return Response(data)


class SeedStatsView(APIView):
    """
    Get seed statistics.
    
    GET /api/seeds/stats/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get aggregate statistics."""
        from django.db.models import Count
        
        total = Seed.objects.count()
        by_status = dict(
            Seed.objects.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        promotable = Seed.objects.filter(
            status='valid',
            is_reachable=True,
            is_crawlable=True,
            promoted_to__isnull=True
        ).count()
        
        return Response({
            'total': total,
            'by_status': by_status,
            'promotable': promotable,
            'pending_validation': by_status.get('pending', 0),
        })


class SeedDiscoverEntrypointsView(APIView):
    """
    Discover article entrypoints from a seed URL.
    
    POST /api/seeds/{id}/discover-entrypoints/
    
    Analyzes the seed URL to find potential article listing pages,
    RSS feeds, sitemaps, and other entry points for crawling.
    
    All discovered URLs are:
    - Normalized using URLNormalizer
    - Filtered to same domain as seed
    - De-duplicated by normalized URL
    
    Caps are configurable via settings (PROBE_*) to bound runtime/memory.
    Phase 18: Made caps configurable via settings.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DiscoveryEndpointThrottle]
    
    @property
    def MAX_LINKS_PER_PAGE(self):
        return getattr(settings, 'PROBE_MAX_LINKS_PER_PAGE', 100)
    
    @property
    def MAX_TOTAL_ENTRYPOINTS(self):
        return getattr(settings, 'PROBE_MAX_TOTAL_ENTRYPOINTS', 50)
    
    @property
    def MAX_RESULT_ENTRYPOINTS(self):
        return getattr(settings, 'PROBE_MAX_RESULT_ENTRYPOINTS', 20)
    
    @property
    def MAX_CONTENT_SIZE(self):
        return getattr(settings, 'PROBE_MAX_CONTENT_SIZE', 2 * 1024 * 1024)
    
    @property
    def PAGE_TIMEOUT(self):
        return getattr(settings, 'PROBE_PAGE_TIMEOUT', 10)
    
    def post(self, request, pk):
        """Discover entrypoints from a seed URL."""
        from apps.core.security import SafeHTTPClient, SSRFError, URLNormalizer
        from apps.core.exceptions import ErrorCode
        import re
        
        try:
            seed = Seed.objects.get(pk=pk)
        except Seed.DoesNotExist:
            return Response(
                {'error': {'code': ErrorCode.NOT_FOUND.value, 'message': 'Seed not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        parsed = urlparse(seed.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        seed_domain = parsed.netloc
        
        # Track seen normalized URLs for deduplication
        seen_normalized = set()
        entrypoints = []
        warnings = []
        links_analyzed = 0
        links_truncated = False
        
        def add_entrypoint(url, entry_type, confidence, description, feed_type=None):
            """Add entrypoint with normalization and deduplication."""
            nonlocal links_analyzed
            
            # Check cap on total entrypoints
            if len(entrypoints) >= self.MAX_TOTAL_ENTRYPOINTS:
                return False
            
            links_analyzed += 1
            
            try:
                # Normalize URL
                normalized = URLNormalizer.normalize(url)
            except Exception:
                normalized = url
            
            # Check same domain
            try:
                entry_parsed = urlparse(url)
                if entry_parsed.netloc and entry_parsed.netloc != seed_domain:
                    return  # Skip off-domain URLs
            except Exception:
                return
            
            # Check for duplicates
            if normalized in seen_normalized:
                return
            seen_normalized.add(normalized)
            
            entry = {
                'url': url,
                'normalized_url': normalized,
                'type': entry_type,
                'confidence': confidence,
                'description': description,
            }
            if feed_type:
                entry['feed_type'] = feed_type
            entrypoints.append(entry)
            return True
        
        # Use configurable timeout
        client = SafeHTTPClient(timeout=(5, self.PAGE_TIMEOUT), max_retries=2)
        
        try:
            # Check common RSS feed locations
            rss_paths = [
                '/feed', '/rss', '/rss.xml', '/feed.xml', '/atom.xml',
                '/feeds/posts/default', '/blog/feed', '/news/feed',
            ]
            for path in rss_paths:
                try:
                    url = f"{base_url}{path}"
                    response = client.head(url)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'atom' in content_type:
                            add_entrypoint(url, 'rss', 90, 'Atom feed detected', 'atom')
                        elif any(ct in content_type for ct in ['xml', 'rss']):
                            add_entrypoint(url, 'rss', 90, 'RSS feed detected', 'rss')
                except Exception:
                    pass
            
            # Check sitemap
            sitemap_paths = ['/sitemap.xml', '/sitemap_index.xml', '/sitemap-news.xml']
            for path in sitemap_paths:
                try:
                    url = f"{base_url}{path}"
                    response = client.head(url)
                    if response.status_code == 200:
                        sitemap_type = 'news' if 'news' in path else 'index' if 'index' in path else 'standard'
                        add_entrypoint(url, 'sitemap', 85, 'XML sitemap found', sitemap_type)
                except Exception:
                    pass
            
            # Analyze main page for article listing patterns
            try:
                response = client.get(seed.url)
                content = response.text
                
                # Truncate content if exceeds max size (prevents DoS on large pages)
                if len(content) > self.MAX_CONTENT_SIZE:
                    content = content[:self.MAX_CONTENT_SIZE]
                    warnings.append(f"Content truncated: page size exceeded {self.MAX_CONTENT_SIZE // (1024*1024)}MB limit")
                
                # Look for RSS link in HTML
                rss_links = re.findall(
                    r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                    content, re.IGNORECASE
                )
                for feed_type, href in rss_links:
                    feed_url = href if href.startswith('http') else f"{base_url}{href}"
                    add_entrypoint(feed_url, 'rss', 95, f'{feed_type.upper()} feed from HTML link', feed_type.lower())
                
                # Look for category/archive pages
                category_patterns = [
                    r'href=["\']([^"\']*(?:/category/|/categories/|/topic/|/tag/)[^"\']+)["\']',
                    r'href=["\']([^"\']*(?:/archive|/news|/blog|/articles)[^"\']*)["\']',
                ]
                for pattern in category_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    # Cap links analyzed per page
                    for match in matches[:self.MAX_LINKS_PER_PAGE]:
                        if len(entrypoints) >= self.MAX_TOTAL_ENTRYPOINTS:
                            links_truncated = True
                            break
                        page_url = match if match.startswith('http') else f"{base_url}{match}"
                        add_entrypoint(page_url, 'listing', 70, 'Category/archive page')
                    if links_truncated:
                        break
                
                # Check if we hit any truncation
                total_matches = sum(len(re.findall(p, content, re.IGNORECASE)) for p in category_patterns)
                if total_matches > self.MAX_LINKS_PER_PAGE:
                    links_truncated = True
                    warnings.append(f"Truncated link analysis: {total_matches} links found, analyzed first {self.MAX_LINKS_PER_PAGE}")
                
            except Exception as e:
                logger.warning(f"Error analyzing page for entrypoints: {e}")
        
        except SSRFError as e:
            return Response({
                'error': {'code': ErrorCode.SSRF_BLOCKED.value, 'message': str(e)},
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error discovering entrypoints: {e}")
            return Response({
                'error': {'code': ErrorCode.NETWORK_ERROR.value, 'message': str(e)},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()
        
        # Sort by confidence
        entrypoints.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Limit results
        result_entrypoints = entrypoints[:self.MAX_RESULT_ENTRYPOINTS]
        
        # Add truncation warning if applicable
        if len(entrypoints) > self.MAX_RESULT_ENTRYPOINTS:
            warnings.append(f"Showing top {self.MAX_RESULT_ENTRYPOINTS} of {len(entrypoints)} candidates")
        
        response_data = {
            'seed_id': str(seed.id),
            'seed_url': seed.url,
            'entrypoints': result_entrypoints,
            'count': len(result_entrypoints),
            'total_found': len(entrypoints),
            'links_analyzed': links_analyzed,
            'message': f"Discovered {len(result_entrypoints)} potential entrypoints",
        }
        
        if warnings:
            response_data['warnings'] = warnings
        
        return Response(response_data)


class SeedTestCrawlView(APIView):
    """
    Perform a test crawl on a seed URL.
    
    POST /api/seeds/{id}/test-crawl/
    
    Request body:
        entrypoint_url: Override URL to crawl (optional, defaults to seed.url)
        max_pages: Maximum pages to fetch (default: 10, capped by settings)
        max_articles: Maximum articles to return (default: 5, capped by settings)
        follow_links: Whether to follow links (default: true)
    
    Executes a limited crawl to sample articles from the seed,
    returning a preview of what would be captured.
    
    Caps are configurable via settings (PROBE_*) to bound runtime/memory.
    Phase 18: Made caps configurable via settings.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProbeEndpointThrottle]
    
    @property
    def MAX_PAGES(self):
        return getattr(settings, 'PROBE_MAX_PAGES', 20)
    
    @property
    def MAX_ARTICLES(self):
        return getattr(settings, 'PROBE_MAX_ARTICLES', 10)
    
    @property
    def MAX_LINKS_PER_PAGE(self):
        return getattr(settings, 'PROBE_MAX_LINKS_PER_PAGE', 100)
    
    @property
    def MAX_CONTENT_SIZE(self):
        return getattr(settings, 'PROBE_MAX_CONTENT_SIZE', 2 * 1024 * 1024)
    
    @property
    def PAGE_TIMEOUT(self):
        return getattr(settings, 'PROBE_PAGE_TIMEOUT', 10)
    
    def post(self, request, pk):
        """Test crawl a seed URL."""
        from apps.core.security import SafeHTTPClient, SSRFError
        from apps.core.exceptions import ErrorCode
        import re
        
        try:
            seed = Seed.objects.get(pk=pk)
        except Seed.DoesNotExist:
            return Response(
                {'error': {'code': ErrorCode.NOT_FOUND.value, 'message': 'Seed not found'}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse request options - enforce server-side caps
        entrypoint_url = request.data.get('entrypoint_url', seed.url)
        max_pages = min(int(request.data.get('max_pages', 10)), self.MAX_PAGES)
        max_articles = min(int(request.data.get('max_articles', 5)), self.MAX_ARTICLES)
        follow_links = request.data.get('follow_links', True)
        
        # Validate entrypoint_url is same domain as seed
        parsed_seed = urlparse(seed.url)
        parsed_entry = urlparse(entrypoint_url)
        if parsed_seed.netloc != parsed_entry.netloc:
            return Response({
                'error': {'code': ErrorCode.VALIDATION_ERROR.value, 
                          'message': f'entrypoint_url must be on same domain as seed ({parsed_seed.netloc})'},
            }, status=status.HTTP_400_BAD_REQUEST)
        
        base_url = f"{parsed_entry.scheme}://{parsed_entry.netloc}"
        
        sample_articles = []
        crawl_stats = {
            'pages_fetched': 0,
            'max_pages': max_pages,
            'links_found': 0,
            'links_analyzed': 0,
            'articles_detected': 0,
            'entrypoint_url': entrypoint_url,
            'errors': [],
            'warnings': [],
        }
        
        client = SafeHTTPClient(timeout=(5, self.PAGE_TIMEOUT), max_retries=1)
        
        try:
            # Fetch entrypoint page
            response = client.get(entrypoint_url)
            crawl_stats['pages_fetched'] += 1
            content = response.text
            
            # Truncate content if exceeds max size
            content_truncated = False
            if len(content) > self.MAX_CONTENT_SIZE:
                content = content[:self.MAX_CONTENT_SIZE]
                content_truncated = True
                crawl_stats['warnings'].append(
                    f"Entrypoint content truncated: exceeded {self.MAX_CONTENT_SIZE // (1024*1024)}MB limit"
                )
            
            # Extract all links
            links = re.findall(r'href=["\']([^"\']+)["\']', content)
            internal_links = []
            
            for link in links:
                # Normalize link
                if link.startswith('/'):
                    link = f"{base_url}{link}"
                elif not link.startswith('http'):
                    continue
                
                # Only follow internal links
                if parsed_entry.netloc in link:
                    internal_links.append(link)
            
            internal_links = list(set(internal_links))
            total_links_found = len(internal_links)
            crawl_stats['links_found'] = total_links_found
            
            # Cap links analyzed per page
            if total_links_found > self.MAX_LINKS_PER_PAGE:
                internal_links = internal_links[:self.MAX_LINKS_PER_PAGE]
                crawl_stats['warnings'].append(
                    f"Truncated link analysis: {total_links_found} links found, analyzed first {self.MAX_LINKS_PER_PAGE}"
                )
            crawl_stats['links_analyzed'] = len(internal_links)
            
            # Filter for likely article URLs
            article_patterns = [
                r'/\d{4}/\d{2}/',  # Date-based: /2024/01/
                r'/article/',
                r'/news/',
                r'/post/',
                r'/blog/',
                r'/story/',
                r'-\d+\.html$',
                r'/p/[a-z0-9-]+$',
            ]
            
            article_links = []
            for link in internal_links:
                if any(re.search(p, link) for p in article_patterns):
                    article_links.append(link)
            
            # If no pattern matches, try fetching some links
            if not article_links and follow_links:
                article_links = internal_links[:max_articles * 2]
            
            # Limit pages to fetch based on max_pages
            pages_remaining = max_pages - 1  # Already fetched entrypoint
            
            # Fetch sample articles
            for article_url in article_links[:pages_remaining]:
                if len(sample_articles) >= max_articles:
                    break
                if crawl_stats['pages_fetched'] >= max_pages:
                    break
                
                try:
                    art_response = client.get(article_url)
                    crawl_stats['pages_fetched'] += 1
                    art_content = art_response.text
                    
                    # Truncate content if exceeds max size
                    if len(art_content) > self.MAX_CONTENT_SIZE:
                        art_content = art_content[:self.MAX_CONTENT_SIZE]
                    
                    # Extract title
                    title_match = re.search(
                        r'<title[^>]*>([^<]+)</title>',
                        art_content, re.IGNORECASE
                    )
                    title = title_match.group(1).strip() if title_match else 'Unknown'
                    
                    # Extract meta description
                    desc_match = re.search(
                        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                        art_content, re.IGNORECASE
                    )
                    if not desc_match:
                        desc_match = re.search(
                            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
                            art_content, re.IGNORECASE
                        )
                    description = desc_match.group(1).strip()[:200] if desc_match else None
                    
                    # Check if it looks like an article
                    is_article = any([
                        '<article' in art_content.lower(),
                        'class="article' in art_content.lower(),
                        'class="post' in art_content.lower(),
                        'itemprop="articleBody"' in art_content,
                    ])
                    
                    # Extract publish date
                    date_match = re.search(
                        r'<time[^>]+datetime=["\']([^"\']+)["\']',
                        art_content
                    )
                    published_at = date_match.group(1) if date_match else None
                    
                    # Estimate word count
                    # Remove HTML tags for rough word count
                    text_content = re.sub(r'<[^>]+>', '', art_content)
                    word_count = len(text_content.split())
                    
                    if is_article or word_count > 200:
                        sample_articles.append({
                            'url': article_url,
                            'title': title,
                            'description': description,
                            'published_at': published_at,
                            'word_count': word_count,
                            'is_article': is_article,
                        })
                        crawl_stats['articles_detected'] += 1
                        
                except SSRFError as e:
                    crawl_stats['errors'].append(f"SSRF blocked: {article_url}")
                except Exception as e:
                    crawl_stats['errors'].append(f"Error fetching {article_url}: {str(e)[:50]}")
        
        except SSRFError as e:
            return Response({
                'error': {'code': ErrorCode.SSRF_BLOCKED.value, 'message': str(e)},
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in test crawl: {e}")
            return Response({
                'error': {'code': ErrorCode.NETWORK_ERROR.value, 'message': str(e)},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()
        
        # Update seed with test crawl results
        seed.article_count_estimate = crawl_stats['articles_detected']
        seed.has_articles = crawl_stats['articles_detected'] > 0
        seed.save()
        
        return Response({
            'seed_id': str(seed.id),
            'seed_url': seed.url,
            'sample_articles': sample_articles,
            'stats': crawl_stats,
            'success': crawl_stats['articles_detected'] > 0,
            'message': f"Test crawl complete: found {crawl_stats['articles_detected']} articles",
        })
