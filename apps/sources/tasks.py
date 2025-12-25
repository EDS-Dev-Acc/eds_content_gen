"""
Celery tasks for source crawling.

Phase 10.2: Extended to support parent jobs and config overrides.
Phase 14.1: Added error taxonomy for normalized error codes.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _classify_error(exc):
    """
    Classify an exception into a normalized error code.
    
    Returns tuple of (error_code, error_message).
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    
    # Network errors
    if exc_type in ('ConnectionError', 'ConnectTimeout', 'ReadTimeout', 'Timeout'):
        return 'NETWORK_TIMEOUT', exc_msg
    if exc_type in ('ConnectionRefused', 'ConnectionReset'):
        return 'NETWORK_REFUSED', exc_msg
    if 'ssl' in exc_msg.lower() or 'certificate' in exc_msg.lower():
        return 'SSL_ERROR', exc_msg
    if 'dns' in exc_msg.lower() or 'name resolution' in exc_msg.lower():
        return 'DNS_ERROR', exc_msg
    
    # HTTP errors
    if '403' in exc_msg or 'forbidden' in exc_msg.lower():
        return 'HTTP_FORBIDDEN', exc_msg
    if '404' in exc_msg or 'not found' in exc_msg.lower():
        return 'HTTP_NOT_FOUND', exc_msg
    if '429' in exc_msg or 'rate limit' in exc_msg.lower():
        return 'RATE_LIMITED', exc_msg
    if '5' in exc_msg[:3] and exc_msg[1:2].isdigit():  # 5xx errors
        return 'HTTP_SERVER_ERROR', exc_msg
    
    # Parsing errors
    if exc_type in ('JSONDecodeError', 'XMLSyntaxError', 'ParseError'):
        return 'PARSE_ERROR', exc_msg
    if 'encoding' in exc_msg.lower() or 'decode' in exc_msg.lower():
        return 'ENCODING_ERROR', exc_msg
    
    # Robots.txt
    if 'robot' in exc_msg.lower() or 'disallowed' in exc_msg.lower():
        return 'ROBOTS_BLOCKED', exc_msg
    
    # Generic
    return 'UNKNOWN_ERROR', exc_msg


@shared_task(bind=True, max_retries=3)
def crawl_source(
    self, 
    source_id, 
    crawl_job_id=None,
    parent_job_id=None,
    config_overrides=None,
    request_id=None
):
    """
    Crawl a single source asynchronously.

    Args:
        source_id: UUID of the source to crawl
        crawl_job_id: Optional pre-created CrawlJob ID
        parent_job_id: Optional parent CrawlJob ID for multi-source runs
        config_overrides: Optional dict of runtime config overrides
        request_id: Optional request ID for log correlation

    Returns:
        dict with crawl results
        
    Phase 18: Enhanced with request_id propagation and improved cancellation handling.
    """
    from apps.sources.models import Source, CrawlJob, CrawlJobSourceResult
    from apps.sources.crawlers import get_crawler

    # Set up logging context with request_id if provided
    log_extra = {'request_id': request_id} if request_id else {}
    
    config_overrides = config_overrides or {}
    crawl_job = None
    source_result = None

    def _check_parent_cancelled():
        """Helper to check if parent job was cancelled."""
        if not parent_job_id:
            return False
        try:
            parent = CrawlJob.objects.only('status').get(id=parent_job_id)
            return parent.status == 'cancelled'
        except CrawlJob.DoesNotExist:
            return True  # Parent gone, treat as cancelled

    try:
        # Get the source
        source = Source.objects.get(id=source_id)
        logger.info(f"Starting crawl task for {source.name}", extra=log_extra)

        # Check for cancellation before starting
        if _check_parent_cancelled():
            logger.info(f"Parent job {parent_job_id} cancelled, skipping {source.name}", extra=log_extra)
            source_result = CrawlJobSourceResult.objects.filter(
                crawl_job_id=parent_job_id,
                source=source
            ).first()
            if source_result:
                source_result.status = 'skipped'
                source_result.error_message = 'Parent job cancelled'
                source_result.completed_at = timezone.now()
                source_result.save()
                _finalize_parent_job(parent_job_id)
            return {'success': False, 'status': 'skipped', 'reason': 'Parent job cancelled'}

        # Handle job tracking
        if crawl_job_id:
            # Use pre-created job (single source run started via API)
            crawl_job = CrawlJob.objects.get(id=crawl_job_id)
            crawl_job.task_id = self.request.id
            # Check for cancellation
            if crawl_job.status == 'cancelled':
                logger.info(f"Job {crawl_job_id} cancelled, skipping")
                return {'success': False, 'status': 'skipped', 'reason': 'Job cancelled'}
        elif parent_job_id:
            # Multi-source run - update the source result
            parent_job = CrawlJob.objects.get(id=parent_job_id)
            source_result = CrawlJobSourceResult.objects.get(
                crawl_job=parent_job,
                source=source
            )
            source_result.status = 'running'
            source_result.started_at = timezone.now()
            source_result.save()
            # Also create a linked CrawlJob for this source
            crawl_job = CrawlJob.objects.create(
                source=source,
                status='running',
                task_id=self.request.id,
                triggered_by='schedule' if parent_job.triggered_by == 'schedule' else 'api',
                config_overrides=config_overrides,
            )
        else:
            # Legacy: create new crawl job (for scheduled tasks)
            crawl_job = CrawlJob.objects.create(
                source=source,
                status='pending',
                task_id=self.request.id,
                triggered_by='schedule',
            )

        # Update status to running
        if crawl_job.status != 'running':
            crawl_job.status = 'running'
            crawl_job.started_at = timezone.now()
            crawl_job.save()

        # Get crawler with optional config overrides
        crawler_config = source.crawler_config.copy() if source.crawler_config else {}
        crawler_config.update(config_overrides)
        crawler = get_crawler(source, config=crawler_config)
        
        # Execute crawl (TODO: Add periodic cancellation check during crawl)
        results = crawler.crawl()

        # Re-check for cancellation after crawl completes (parent may have been cancelled mid-crawl)
        if _check_parent_cancelled():
            logger.info(f"Parent job {parent_job_id} cancelled after crawl, marking skipped", extra=log_extra)
            if source_result:
                source_result.status = 'skipped'
                source_result.error_message = 'Parent job cancelled during crawl'
                source_result.completed_at = timezone.now()
                source_result.save()
                _finalize_parent_job(parent_job_id)
            return {'success': False, 'status': 'skipped', 'reason': 'Parent job cancelled during crawl'}

        # Update crawl job with results
        crawl_job.status = 'completed'
        crawl_job.completed_at = timezone.now()
        crawl_job.total_found = results.get('total_found', 0)
        crawl_job.new_articles = results.get('new_articles', 0)
        crawl_job.duplicates = results.get('duplicates', 0)
        crawl_job.errors = results.get('errors', 0)
        crawl_job.pages_crawled = results.get('pages_crawled', 1)
        crawl_job.save()

        # Update source result if multi-source
        if source_result:
            source_result.status = 'completed'
            source_result.completed_at = timezone.now()
            source_result.articles_found = results.get('total_found', 0)
            source_result.articles_new = results.get('new_articles', 0)
            source_result.articles_duplicate = results.get('duplicates', 0)
            source_result.pages_crawled = results.get('pages_crawled', 1)
            source_result.errors_count = results.get('errors', 0)
            source_result.save()
            
            # Update parent job aggregates atomically
            _finalize_parent_job(parent_job_id)

        logger.info(
            f"Crawl complete for {source.name}: "
            f"{results.get('new_articles', 0)} new articles"
        )

        return {
            'success': True,
            'source_id': str(source_id),
            'source_name': source.name,
            'results': results,
            'crawl_job_id': str(crawl_job.id)
        }

    except Source.DoesNotExist:
        logger.error(f"Source {source_id} not found")
        return {
            'success': False,
            'error': 'Source not found'
        }

    except Exception as exc:
        logger.error(f"Error crawling source {source_id}: {exc}")

        # Classify the error for taxonomy
        error_code, error_message = _classify_error(exc)

        # Update crawl job as failed
        if crawl_job:
            try:
                crawl_job.status = 'failed'
                crawl_job.completed_at = timezone.now()
                crawl_job.error_message = error_message
                crawl_job.save()
            except:
                pass

        # Update source result if multi-source
        if source_result:
            try:
                source_result.status = 'failed'
                source_result.completed_at = timezone.now()
                source_result.error_code = error_code
                source_result.error_message = error_message
                source_result.save()
                _finalize_parent_job(parent_job_id)
            except:
                pass

        # Retry with exponential backoff
        raise self.retry(
            exc=exc,
            countdown=60 * (2 ** self.request.retries)
        )


def _finalize_parent_job(parent_job_id):
    """
    Aggregate results from child source results to parent job.
    
    This function is called after each child task completes. It uses
    select_for_update to prevent race conditions when multiple children
    complete concurrently. Only one caller will finalize the parent.
    
    Status logic:
    - If any children are running/pending → parent stays running
    - If all completed → parent completed  
    - If any failed AND none running/pending → parent failed (if no successes)
    - If some completed, some failed → parent completed with warning
    - If all skipped → parent cancelled
    
    Idempotency: Uses finalized_at timestamp as guard. Once set, status changes
    are blocked but totals may still be updated for consistency.
    
    Transaction safety: Uses select_for_update() to serialize concurrent updates.
    
    Phase 18: Enhanced with finalized_at guard and improved status logic.
    """
    from apps.sources.models import CrawlJob
    from django.db.models import Sum, Count
    from django.db import transaction
    
    if not parent_job_id:
        return
    
    try:
        with transaction.atomic():
            # Lock the parent job row to serialize concurrent finalizations
            parent_job = CrawlJob.objects.select_for_update(nowait=False).get(id=parent_job_id)
            
            # Check finalized_at as idempotency guard (more robust than status check)
            already_finalized = parent_job.finalized_at is not None
            
            results = parent_job.source_results.all()
            
            # Aggregate totals using DB-level aggregation (efficient)
            agg = results.aggregate(
                total_found=Sum('articles_found'),
                new_articles=Sum('articles_new'),
                duplicates=Sum('articles_duplicate'),
                pages=Sum('pages_crawled'),
                error_count=Sum('errors_count'),
            )
            
            # Always update totals (even if already finalized, for consistency)
            parent_job.total_found = agg['total_found'] or 0
            parent_job.new_articles = agg['new_articles'] or 0
            parent_job.duplicates = agg['duplicates'] or 0
            parent_job.pages_crawled = agg['pages'] or 0
            parent_job.errors = agg['error_count'] or 0
            
            # Get status counts efficiently with single query
            status_counts = results.values('status').annotate(count=Count('id'))
            status_map = {s['status']: s['count'] for s in status_counts}
            
            pending_count = status_map.get('pending', 0)
            running_count = status_map.get('running', 0)
            failed_count = status_map.get('failed', 0)
            completed_count = status_map.get('completed', 0)
            skipped_count = status_map.get('skipped', 0)
            pending_or_running = pending_count + running_count
            total_count = sum(status_map.values())
            
            # Only update status if not already finalized
            if not already_finalized:
                # Determine parent status
                if pending_or_running > 0:
                    # Still processing - don't finalize yet
                    parent_job.status = 'running'
                elif total_count == 0:
                    # No children yet (shouldn't happen, but defensive)
                    parent_job.status = 'pending'
                elif skipped_count == total_count:
                    # All skipped (cancelled)
                    parent_job.status = 'cancelled'
                    parent_job.completed_at = timezone.now()
                    parent_job.finalized_at = timezone.now()
                    logger.info(f"Parent job {parent_job_id} finalized as cancelled (all children skipped)")
                elif failed_count == total_count:
                    # All failed - parent failed
                    parent_job.status = 'failed'
                    parent_job.completed_at = timezone.now()
                    parent_job.finalized_at = timezone.now()
                    parent_job.error_message = f"All {total_count} sources failed"
                    logger.info(f"Parent job {parent_job_id} finalized as failed (all {total_count} failed)")
                elif completed_count > 0:
                    # Some or all completed - parent completed (partial success is success)
                    parent_job.status = 'completed'
                    parent_job.completed_at = timezone.now()
                    parent_job.finalized_at = timezone.now()
                    warnings = []
                    if failed_count > 0:
                        warnings.append(f"{failed_count} sources failed")
                    if skipped_count > 0:
                        warnings.append(f"{skipped_count} sources skipped")
                    if warnings:
                        parent_job.error_message = "; ".join(warnings)
                    logger.info(f"Parent job {parent_job_id} finalized as completed ({completed_count} succeeded, {failed_count} failed, {skipped_count} skipped)")
                else:
                    # Edge case: all failed or skipped with no completions
                    parent_job.status = 'failed'
                    parent_job.completed_at = timezone.now()
                    parent_job.finalized_at = timezone.now()
                    parent_job.error_message = f"{failed_count} failed, {skipped_count} skipped"
                    logger.info(f"Parent job {parent_job_id} finalized as failed ({failed_count} failed, {skipped_count} skipped)")
            else:
                logger.debug(f"Parent job {parent_job_id} already finalized at {parent_job.finalized_at}, updating totals only")
            
            parent_job.save()
        
    except CrawlJob.DoesNotExist:
        logger.warning(f"Parent job {parent_job_id} not found during finalization")
    except Exception as e:
        logger.error(f"Error finalizing parent job {parent_job_id}: {e}", exc_info=True)


@shared_task
def crawl_all_active_sources():
    """
    Queue crawl tasks for all active sources.
    This task is typically scheduled to run hourly.

    Returns:
        dict with summary
    """
    from apps.sources.models import Source

    logger.info("Starting crawl_all_active_sources task")

    # Get all active sources
    sources = Source.objects.filter(status='active')
    total = sources.count()

    logger.info(f"Found {total} active sources")

    # Queue individual crawl tasks
    queued = 0
    for source in sources:
        try:
            crawl_source.delay(str(source.id))
            queued += 1
        except Exception as e:
            logger.error(f"Error queuing crawl for {source.name}: {e}")

    result = {
        'total_sources': total,
        'tasks_queued': queued,
    }

    logger.info(f"Queued {queued}/{total} crawl tasks")
    return result
