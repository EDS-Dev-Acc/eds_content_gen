"""
Discovery Pipeline Tasks.

Phase 16: Celery tasks for automated seed discovery with sync fallback.

Tasks:
- run_discovery: Main discovery orchestrator
- process_discovery_query: Execute single query with connector
- classify_and_score_captures: Process captured pages
- cleanup_old_captures: TTL-based capture cleanup

Sync Fallback:
When DISCOVERY_PIPELINE_ENABLED=False or Celery unavailable,
provides sync execution via management command.
"""

import logging
import uuid
from datetime import timedelta
from typing import Dict, List, Optional, Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Check if Celery is available
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Create a no-op decorator
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


def is_discovery_enabled() -> bool:
    """Check if discovery pipeline is enabled."""
    return getattr(settings, 'DISCOVERY_PIPELINE_ENABLED', False)


def is_celery_available() -> bool:
    """Check if Celery broker is reachable."""
    if not CELERY_AVAILABLE:
        return False
    
    try:
        from config.celery import app
        conn = app.connection()
        conn.ensure_connection(max_retries=1)
        conn.close()
        return True
    except Exception:
        return False


# =============================================================================
# Main Discovery Task
# =============================================================================

@shared_task(bind=True, max_retries=2, soft_time_limit=3600)
def run_discovery(
    self,
    discovery_run_id: str,
    theme: str,
    geography: Optional[List[str]] = None,
    entity_types: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    max_queries: int = 50,
    max_results_per_query: int = 20,
    connectors: Optional[List[str]] = None,
):
    """
    Main discovery orchestrator task.
    
    Args:
        discovery_run_id: UUID of DiscoveryRun record
        theme: Discovery theme (e.g., "logistics companies")
        geography: Target countries
        entity_types: Target entity types
        keywords: Additional keywords
        max_queries: Maximum queries to generate
        max_results_per_query: Max results per query
        connectors: Connector types to use ['serp', 'rss', 'html_directory']
    """
    from apps.seeds.models import DiscoveryRun, Seed, SeedRawCapture
    from apps.seeds.discovery import QueryGenerator, get_connector
    from apps.seeds.discovery.query_generator import TargetBrief
    
    # Load discovery run
    try:
        run = DiscoveryRun.objects.get(id=discovery_run_id)
    except DiscoveryRun.DoesNotExist:
        logger.error(f"Discovery run {discovery_run_id} not found")
        return {'error': 'Run not found'}
    
    # Update status
    run.status = 'running'
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at', 'updated_at'])
    
    try:
        # Generate queries
        brief = TargetBrief(
            theme=theme,
            geography=geography or [],
            entity_types=entity_types or [],
            keywords=keywords or [],
        )
        
        generator = QueryGenerator(use_llm=True)
        queries = generator.generate(brief, max_queries=max_queries)
        
        run.queries_generated = len(queries)
        run.save(update_fields=['queries_generated', 'updated_at'])
        
        logger.info(f"Discovery {discovery_run_id}: Generated {len(queries)} queries")
        
        # Execute queries
        connector_types = connectors or ['html_directory', 'rss']
        all_candidates = []
        all_captures = []
        
        for query in queries:
            for conn_type in connector_types:
                try:
                    connector = get_connector(conn_type)
                    candidates, captures = connector.discover(
                        query=query.query,
                        max_results=max_results_per_query,
                    )
                    all_candidates.extend(candidates)
                    all_captures.extend(captures)
                except Exception as e:
                    logger.warning(f"Connector {conn_type} failed for query '{query.query}': {e}")
        
        run.urls_discovered = len(all_candidates)
        run.captures_created = len(all_captures)
        run.save(update_fields=['urls_discovered', 'captures_created', 'updated_at'])
        
        # Create seeds from candidates
        seeds_created = _create_seeds_from_candidates(
            candidates=all_candidates,
            captures=all_captures,
            discovery_run_id=discovery_run_id,
            entity_types=entity_types or [],
            geography=geography or [],
            keywords=keywords or [],
        )
        
        run.seeds_created = seeds_created
        run.status = 'completed'
        run.completed_at = timezone.now()
        run.save(update_fields=['seeds_created', 'status', 'completed_at', 'updated_at'])
        
        logger.info(f"Discovery {discovery_run_id}: Created {seeds_created} seeds")
        
        return {
            'discovery_run_id': discovery_run_id,
            'queries_generated': len(queries),
            'urls_discovered': len(all_candidates),
            'captures_created': len(all_captures),
            'seeds_created': seeds_created,
        }
        
    except Exception as e:
        logger.exception(f"Discovery {discovery_run_id} failed: {e}")
        run.status = 'failed'
        run.error_message = str(e)
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
        raise


def _create_seeds_from_candidates(
    candidates: List,
    captures: List,
    discovery_run_id: str,
    entity_types: List[str],
    geography: List[str],
    keywords: List[str],
) -> int:
    """Create Seed records from discovered candidates."""
    from apps.seeds.models import Seed, SeedRawCapture
    from apps.seeds.discovery import SeedClassifier, SeedScorer
    from apps.core.security import URLNormalizer
    
    classifier = SeedClassifier()
    scorer = SeedScorer(
        target_entity_types=entity_types,
        target_countries=[g.upper()[:2] for g in geography],  # Convert to country codes
        target_keywords=keywords,
    )
    
    created_count = 0
    seen_urls = set()
    
    # Build capture lookup
    capture_by_url = {}
    for capture in captures:
        if hasattr(capture, 'url'):
            capture_by_url[capture.url] = capture
    
    for candidate in candidates:
        # Dedupe
        try:
            normalized = URLNormalizer.normalize(candidate.url)
        except Exception:
            normalized = candidate.url
        
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        
        # Check if seed already exists
        if Seed.objects.filter(normalized_url=normalized).exists():
            continue
        
        # Get capture for classification
        capture = capture_by_url.get(candidate.url)
        content_sample = None
        
        if capture:
            try:
                content_sample = capture.get_body()[:50000].decode('utf-8', errors='replace')
            except Exception:
                pass
        
        # Classify
        classification = classifier.classify(
            html_content=content_sample or '',
            url=candidate.url,
        )
        
        # Score
        score = scorer.score(
            classification=classification,
            url=candidate.url,
            content_sample=content_sample,
            discovery_method=candidate.discovery_method,
        )
        
        # Skip rejected candidates
        if score.is_spam or score.is_parked:
            continue
        
        # Create seed
        try:
            with transaction.atomic():
                seed = Seed.objects.create(
                    url=candidate.url,
                    normalized_url=normalized,
                    domain=candidate.domain,
                    seed_type=_map_page_type_to_seed_type(classification.page_type),
                    confidence=candidate.confidence,
                    country=classification.country_codes[0] if classification.country_codes else '',
                    topics=keywords,
                    query_used=candidate.query_used,
                    referrer_url=candidate.referrer_url,
                    discovery_run_id=uuid.UUID(discovery_run_id),
                    relevance_score=score.relevance_score,
                    utility_score=score.utility_score,
                    freshness_score=score.freshness_score,
                    authority_score=score.authority_score,
                    overall_score=score.overall_score,
                    scrape_plan_hint=_suggest_scrape_plan(classification),
                    recommended_entrypoints=classification.sitemap_urls + classification.feed_urls,
                    import_source='discovery',
                    status='pending',
                    review_status='pending',
                )
                
                # Store capture if available
                if capture and getattr(settings, 'CAPTURE_STORAGE_ENABLED', True):
                    SeedRawCapture.objects.create(
                        url=capture.url,
                        final_url=capture.final_url,
                        status_code=capture.status_code,
                        headers=capture.headers,
                        content_type=capture.content_type,
                        body_hash=capture.body_hash,
                        body_size=capture.body_size,
                        body_compressed=capture.body_compressed,
                        body_path=capture.body_path or '',
                        fetch_mode=capture.fetch_mode,
                        discovery_run_id=uuid.UUID(discovery_run_id),
                        seed=seed,
                    )
                
                created_count += 1
                
        except Exception as e:
            logger.warning(f"Failed to create seed for {candidate.url}: {e}")
    
    return created_count


def _map_page_type_to_seed_type(page_type: str) -> str:
    """Map classifier page type to seed type."""
    mapping = {
        'directory': 'aggregator',
        'association': 'government',  # Close enough
        'gov_registry': 'government',
        'news': 'news',
        'marketplace': 'aggregator',
        'company_homepage': 'blog',  # Default for company sites
    }
    return mapping.get(page_type, 'unknown')


def _suggest_scrape_plan(classification) -> str:
    """Suggest scrape plan based on classification."""
    if classification.has_rss_feed:
        return 'rss_feed'
    if classification.has_sitemap:
        return 'sitemap'
    if classification.has_member_list:
        return 'member_list'
    if classification.has_pagination:
        return 'category_pages'
    return 'manual'


# =============================================================================
# Cleanup Task
# =============================================================================

@shared_task(soft_time_limit=600)
def cleanup_old_captures(days: Optional[int] = None):
    """
    Clean up old captures beyond TTL.
    
    Args:
        days: TTL in days (defaults to CAPTURE_TTL_DAYS setting)
    """
    from apps.seeds.models import SeedRawCapture
    
    ttl_days = days or getattr(settings, 'CAPTURE_TTL_DAYS', 7)
    cutoff = timezone.now() - timedelta(days=ttl_days)
    
    # Get captures to delete
    old_captures = SeedRawCapture.objects.filter(
        created_at__lt=cutoff
    )
    
    count = old_captures.count()
    
    # Delete files first
    for capture in old_captures.iterator():
        capture.delete_file()
    
    # Delete records
    old_captures.delete()
    
    logger.info(f"Cleaned up {count} captures older than {ttl_days} days")
    
    return {'deleted_count': count}


@shared_task(soft_time_limit=300)
def cleanup_failed_discovery_runs(days: int = 30):
    """Clean up old failed discovery runs."""
    from apps.seeds.models import DiscoveryRun
    
    cutoff = timezone.now() - timedelta(days=days)
    
    deleted, _ = DiscoveryRun.objects.filter(
        status='failed',
        created_at__lt=cutoff,
    ).delete()
    
    logger.info(f"Cleaned up {deleted} failed discovery runs older than {days} days")
    
    return {'deleted_count': deleted}


# =============================================================================
# Sync Execution (CLI Fallback)
# =============================================================================

def run_discovery_sync(
    theme: str,
    geography: Optional[List[str]] = None,
    entity_types: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    max_queries: int = 20,
    max_results_per_query: int = 10,
    connectors: Optional[List[str]] = None,
    user=None,
) -> Dict[str, Any]:
    """
    Run discovery synchronously (for CLI or when Celery unavailable).
    
    Returns discovery run result dict.
    """
    from apps.seeds.models import DiscoveryRun
    
    # Create discovery run record
    run = DiscoveryRun.objects.create(
        theme=theme,
        geography=geography or [],
        entity_types=entity_types or [],
        keywords=keywords or [],
        config={
            'max_queries': max_queries,
            'max_results_per_query': max_results_per_query,
            'connectors': connectors or ['html_directory', 'rss'],
        },
        status='pending',
        started_by=user,
    )
    
    # Execute synchronously (call the task function directly)
    result = run_discovery(
        self=None,  # No Celery context
        discovery_run_id=str(run.id),
        theme=theme,
        geography=geography,
        entity_types=entity_types,
        keywords=keywords,
        max_queries=max_queries,
        max_results_per_query=max_results_per_query,
        connectors=connectors,
    )
    
    return result


def start_discovery_async(
    theme: str,
    geography: Optional[List[str]] = None,
    entity_types: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    max_queries: int = 50,
    max_results_per_query: int = 20,
    connectors: Optional[List[str]] = None,
    user=None,
) -> Dict[str, Any]:
    """
    Start discovery asynchronously if Celery available, else sync.
    
    Returns dict with discovery_run_id and execution mode.
    """
    from apps.seeds.models import DiscoveryRun
    
    # Create discovery run record
    run = DiscoveryRun.objects.create(
        theme=theme,
        geography=geography or [],
        entity_types=entity_types or [],
        keywords=keywords or [],
        config={
            'max_queries': max_queries,
            'max_results_per_query': max_results_per_query,
            'connectors': connectors or ['html_directory', 'rss'],
        },
        status='pending',
        started_by=user,
    )
    
    # Check if we can use Celery
    if is_discovery_enabled() and is_celery_available():
        # Queue async task with request_id propagation
        try:
            from apps.core.middleware import celery_request_id_headers
            headers = celery_request_id_headers()
        except Exception:
            headers = None
        
        task = run_discovery.apply_async(
            kwargs={
                'discovery_run_id': str(run.id),
                'theme': theme,
                'geography': geography,
                'entity_types': entity_types,
                'keywords': keywords,
                'max_queries': max_queries,
                'max_results_per_query': max_results_per_query,
                'connectors': connectors,
            },
            headers=headers,
        )
        return {
            'discovery_run_id': str(run.id),
            'task_id': task.id,
            'mode': 'async',
        }
    else:
        # Execute synchronously
        logger.info("Celery unavailable, running discovery synchronously")
        run_discovery_sync(
            theme=theme,
            geography=geography,
            entity_types=entity_types,
            keywords=keywords,
            max_queries=max_queries,
            max_results_per_query=max_results_per_query,
            connectors=connectors,
            user=user,
        )
        return {
            'discovery_run_id': str(run.id),
            'task_id': None,
            'mode': 'sync',
        }
