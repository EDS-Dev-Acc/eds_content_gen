"""
Celery tasks for source crawling.

Phase 10.2: Extended to support parent jobs and config overrides.
Phase 14.1: Added error taxonomy for normalized error codes.
"""

from celery import shared_task
from django.utils import timezone
import logging
import random

logger = logging.getLogger(__name__)


RETRY_POLICIES = {
    'NETWORK_TIMEOUT': {'max_attempts': 5, 'backoff': 60, 'jitter': 30},
    'NETWORK_REFUSED': {'max_attempts': 4, 'backoff': 90, 'jitter': 30},
    'DNS_ERROR': {'max_attempts': 4, 'backoff': 120, 'jitter': 60},
    'SSL_ERROR': {'max_attempts': 3, 'backoff': 120, 'jitter': 60},
    'RATE_LIMITED': {'max_attempts': 5, 'backoff': 120, 'jitter': 60},
    'HTTP_SERVER_ERROR': {'max_attempts': 4, 'backoff': 90, 'jitter': 45},
    'UNKNOWN_ERROR': {'max_attempts': 3, 'backoff': 60, 'jitter': 30},
}

NON_RETRIABLE_ERRORS = {
    'HTTP_FORBIDDEN',
    'HTTP_NOT_FOUND',
    'ROBOTS_BLOCKED',
    'PARSE_ERROR',
    'ENCODING_ERROR',
}

DEFAULT_RETRY_POLICY = {'max_attempts': 3, 'backoff': 60, 'jitter': 30}


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


def _get_retry_decision(error_code, retries, task_max_retries):
    """
    Determine retry allowance and delay based on error code.

    Args:
        error_code: normalized error code
        retries: current retry count from Celery (0-based)
        task_max_retries: The max_retries value set on the task.

    Returns:
        tuple of (should_retry: bool, max_attempts: int, countdown_seconds: int | None)
    """
    policy = RETRY_POLICIES.get(error_code, DEFAULT_RETRY_POLICY)
    max_attempts = policy['max_attempts']
    current_attempt = retries + 1  # include the failed attempt

    # Celery's retries are 0-indexed. A task with max_retries=8 can be retried 8 times (retries will be 0 through 7).
    if error_code in NON_RETRIABLE_ERRORS or current_attempt >gt; max_attempts or retries >=t;= task_max_retries:
        return False, max_attempts, None

    MAX_BACKOFF_SECONDS = 3600  # cap backoff at 1 hour
    backoff = min(policy['backoff'] * (2 ** retries), MAX_BACKOFF_SECONDS)
    jitter = random.uniform(0, policy.get('jitter', 0))
    countdown = int(backoff + jitter)
    return True, max_attempts, countdown


@shared_task(bind=True, max_retries=8)
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
    from apps.sources.crawlers.exceptions import CrawlCancelled

    # Set up logging context with request_id and job identifiers if provided
    log_extra = {}
    if request_id:
        log_extra['request_id'] = request_id
    if parent_job_id:
        log_extra['parent_job_id'] = str(parent_job_id)
    if crawl_job_id:
        log_extra['crawl_job_id'] = str(crawl_job_id)
    
    config_overrides = config_overrides or {}
    crawl_job = None
    source_result = None

    def _check_parent_cancelled():
        """Helper to check if parent job was cancelled/paused."""
        if not parent_job_id:
            return False
        try:
            parent = CrawlJob.objects.only('status').get(id=parent_job_id)
            return parent.status in ('cancelled', 'paused')
        except CrawlJob.DoesNotExist:
            return True  # Parent gone, treat as cancelled

    def _make_cancel_checker(job_id=None, parent_id=None):
        """Create a cancellation checker callable for crawlers."""
        def _check():
            # Check child job first (single-source or per-source job)
            if job_id:
                try:
                    job_status = CrawlJob.objects.only('status').get(id=job_id).status
                    if job_status in ('paused', 'cancelled', 'stopped'):
                        return f"Job {job_status}"
                except CrawlJob.DoesNotExist:
                    return "Job missing"

            # Check parent (multi-source) status
            if parent_id:
                try:
                    parent_status = CrawlJob.objects.only('status').get(id=parent_id).status
                    if parent_status in ('paused', 'cancelled', 'stopped'):
                        return f"Parent {parent_status}"
                except CrawlJob.DoesNotExist:
                    return "Parent missing"

            return None

        return _check

    try:
        # Get the source
        source = Source.objects.get(id=source_id)
        logger.info(f"Starting crawl task for {source.name}", extra=log_extra)

        # Check for cancellation before starting
        if _check_parent_cancelled():
            logger.info(f"Parent job {parent_job_id} cancelled/paused, skipping {source.name}", extra=log_extra)
            source_result = CrawlJobSourceResult.objects.filter(
                crawl_job_id=parent_job_id,
                source=source
            ).first()
            if source_result:
                source_result.status = 'skipped'
                source_result.error_message = 'Parent job cancelled/paused'
                source_result.completed_at = timezone.now()
                source_result.save()
                _finalize_parent_job(parent_job_id)
            return {'success': False, 'status': 'skipped', 'reason': 'Parent job cancelled/paused'}

        # Handle job tracking
        if crawl_job_id:
            # Use pre-created job (single source run started via API)
            crawl_job = CrawlJob.objects.get(id=crawl_job_id)
            crawl_job.task_id = self.request.id
            # Check for cancellation
            if crawl_job.status == 'cancelled':
                logger.info(f"Job {crawl_job_id} cancelled, skipping", extra=log_extra)
                return {'success': False, 'status': 'skipped', 'reason': 'Job cancelled'}
        elif parent_job_id:
            # Multi-source run - update the source result
            parent_job = CrawlJob.objects.get(id=parent_job_id)
            try:
                source_result = CrawlJobSourceResult.objects.get(
                    crawl_job=parent_job,
                    source=source
                )
            except CrawlJobSourceResult.DoesNotExist:
                error_message = f"CrawlJobSourceResult not found for parent job {parent_job_id} and source {source_id}"
                logger.error(error_message, extra=log_extra)
                parent_job.status = 'failed'
                parent_job.error_message = error_message
                parent_job.completed_at = timezone.now()
                parent_job.finalized_at = timezone.now()
                parent_job.save(update_fields=['status', 'error_message', 'completed_at', 'finalized_at'])
                _finalize_parent_job(parent_job_id)
                return {
                    'success': False,
                    'error': 'CrawlJobSourceResult not found'
                }
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
            log_extra['crawl_job_id'] = str(crawl_job.id)
        else:
            # Legacy: create new crawl job (for scheduled tasks)
            crawl_job = CrawlJob.objects.create(
                source=source,
                status='pending',
                task_id=self.request.id,
                triggered_by='schedule',
            )
            log_extra['crawl_job_id'] = str(crawl_job.id)

        # Update status to running
        if crawl_job.status != 'running':
            crawl_job.status = 'running'
            crawl_job.started_at = timezone.now()
            crawl_job.save()

        # Get crawler with optional config overrides
        crawler_config = source.crawler_config.copy() if source.crawler_config else {}
        # Apply selection snapshot overrides if present
        if crawl_job and crawl_job.selection_snapshot:
            snapshot_overrides = crawl_job.selection_snapshot.get('config_overrides') or {}
            crawler_config.update(snapshot_overrides)
        crawler_config.update(config_overrides)
        crawler = get_crawler(source, config=crawler_config)
        crawler.set_cancel_callback(
            _make_cancel_checker(
                job_id=str(crawl_job.id) if crawl_job else crawl_job_id,
                parent_id=parent_job_id,
            )
        )
        
        # Execute crawl with cancellation awareness
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
            f"{results.get('new_articles', 0)} new articles",
            extra=log_extra
        )

        return {
            'success': True,
            'source_id': str(source_id),
            'source_name': source.name,
            'results': results,
            'crawl_job_id': str(crawl_job.id)
        }

    except Source.DoesNotExist:
        error_message = f"Source {source_id} not found"
        logger.error(error_message, extra=log_extra)

        if crawl_job_id:
            crawl_job = CrawlJob.objects.filter(id=crawl_job_id).first()
            if crawl_job:
                crawl_job.status = 'failed'
                crawl_job.completed_at = timezone.now()
                crawl_job.error_message = error_message
                crawl_job.save(update_fields=['status', 'completed_at', 'error_message'])

        if parent_job_id:
            source_result = CrawlJobSourceResult.objects.filter(
                crawl_job_id=parent_job_id,
                source_id=source_id
            ).first()
            if source_result:
                source_result.status = 'failed'
                source_result.completed_at = timezone.now()
                source_result.error_code = 'SOURCE_NOT_FOUND'
                source_result.error_message = error_message
                source_result.save(update_fields=['status', 'completed_at', 'error_code', 'error_message'])
            parent_job = CrawlJob.objects.filter(id=parent_job_id).first()
            if parent_job:
                parent_job.status = 'failed'
                parent_job.error_message = error_message
                parent_job.completed_at = timezone.now()
                parent_job.finalized_at = timezone.now()
                parent_job.save(update_fields=['status', 'error_message', 'completed_at', 'finalized_at'])
            _finalize_parent_job(parent_job_id)

        return {
            'success': False,
            'error': 'Source not found'
        }

    except CrawlCancelled as cancel_exc:
        reason = str(cancel_exc)
        logger.info("Crawl cancelled for source %s: %s", source_id, reason, extra=log_extra)

        # Update crawl job as cancelled
        if crawl_job:
            try:
                crawl_job.status = 'cancelled'
                crawl_job.completed_at = timezone.now()
                crawl_job.error_message = reason
                crawl_job.save()
            except Exception:
                pass

        # Update source result if multi-source
        if source_result:
            try:
                source_result.status = 'skipped'
                source_result.completed_at = timezone.now()
                source_result.error_message = reason
                source_result.save()
                _finalize_parent_job(parent_job_id)
            except Exception:
                pass

        return {
            'success': False,
            'status': 'cancelled',
            'reason': reason,
        }

    except Exception as exc:
        logger.error(f"Error crawling source {source_id}: {exc}", extra=log_extra)

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

        should_retry, max_attempts, countdown = _get_retry_decision(error_code, self.request.retries)
        attempt_number = self.request.retries + 1

        if should_retry and countdown is not None:
            logger.info(
                f"Retrying crawl_source for {source_id} in {countdown}s "
                f"(attempt {attempt_number + 1}/{max_attempts}, error_code={error_code})",
                extra=log_extra,
            )
            raise self.retry(exc=exc, countdown=countdown)

        logger.info(
            f"Not retrying crawl_source for {source_id} "
            f"(attempt {attempt_number}/{max_attempts}, error_code={error_code})",
            extra=log_extra,
        )
        raise


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


@shared_task(bind=True, max_retries=8)
def run_crawl_job(self, job_id):
    """
    Execute a Control Center crawl job.
    
    This task is triggered from the Control Center UI when a user starts a job.
    It handles both single-source and multi-source jobs, with support for:
    - Seeds as starting URLs
    - Config overrides
    - Progress tracking and events
    - Pause/resume capability
    
    Args:
        job_id: UUID of the CrawlJob to execute
        
    Returns:
        dict with execution results
    """
    from apps.sources.models import Source, CrawlJob, CrawlJobEvent, CrawlJobSourceResult, CrawlJobSeed
    from apps.sources.crawlers import get_crawler
    
    logger.info(f"Starting run_crawl_job task for job {job_id}")
    
    try:
        job = CrawlJob.objects.get(id=job_id)
    except CrawlJob.DoesNotExist:
        logger.error(f"CrawlJob {job_id} not found")
        return {'success': False, 'error': 'Job not found'}
    
    # Check if job can be run
    if job.status not in ['queued', 'draft']:
        logger.warning(f"Job {job_id} has status '{job.status}', cannot start")
        return {'success': False, 'error': f'Job status is {job.status}'}
    
    # Update job to running
    job.status = 'running'
    job.started_at = timezone.now()
    job.task_id = self.request.id
    job.save()
    
    # Log start event
    CrawlJobEvent.objects.create(
        crawl_job=job,
        event_type='started',
        severity='info',
        message=f'Job started by Celery task {self.request.id}',
    )
    
    try:
        # Get sources for this job using snapshot to avoid drift
        snapshot_source_ids = job.get_snapshot_source_ids()
        source_results = CrawlJobSourceResult.objects.filter(crawl_job=job).select_related('source')

        if snapshot_source_ids:
            from apps.sources.models import Source  # Local import to avoid circular issues in migrations
            sources = list(Source.objects.filter(id__in=snapshot_source_ids))
            if not sources:
                raise ValueError("Snapshot references no valid sources")
        elif source_results.exists():
            sources = [sr.source for sr in source_results]
        elif job.source:
            sources = [job.source]
        else:
            raise ValueError("Job has no sources configured")

        logger.info(f"Job {job_id} has {len(sources)} sources from snapshot")

        # Ensure source result rows exist for multi-source runs
        if job.is_multi_source:
            existing_result_ids = set(source_results.values_list('source_id', flat=True))
            for source in sources:
                if source.id not in existing_result_ids:
                    CrawlJobSourceResult.objects.create(
                        crawl_job=job,
                        source=source,
                        status='pending',
                    )
            source_results = CrawlJobSourceResult.objects.filter(crawl_job=job).select_related('source')

        # Get seeds for starting URLs (explicit seeds take priority)
        seed_urls = job.get_snapshot_seed_urls()
        
        # If no explicit seeds, use source base URLs as starting points
        if not seed_urls:
            seed_urls = [source.url for source in sources if source.url]
            logger.info(f"Job {job_id} using {len(seed_urls)} source URLs as seeds")
        else:
            logger.info(f"Job {job_id} has {len(seed_urls)} explicit seed URLs")
        
        # Initialize counters
        total_found = 0
        total_new = 0
        total_duplicates = 0
        total_errors = 0
        total_pages = 0
        
        # Process each source
        for source in sources:
            # Check for pause/stop
            job.refresh_from_db()
            if job.status == 'paused':
                logger.info(f"Job {job_id} paused, waiting...")
                CrawlJobEvent.objects.create(
                    crawl_job=job,
                    event_type='paused',
                    severity='info',
                    message='Job paused during execution',
                )
                return {'success': True, 'status': 'paused', 'message': 'Job paused'}
            
            if job.status in ['stopped', 'cancelled']:
                logger.info(f"Job {job_id} stopped/cancelled")
                return {'success': True, 'status': job.status, 'message': f'Job {job.status}'}
            
            logger.info(f"Processing source: {source.name}")
            
            # Update source result if multi-source
            source_result = source_results.filter(source=source).first() if source_results.exists() else None
            if source_result:
                source_result.status = 'running'
                source_result.started_at = timezone.now()
                source_result.save()
            
            try:
                # Build crawler config
                crawler_config = source.crawler_config.copy() if source.crawler_config else {}

                # Apply snapshot overrides first, then runtime overrides
                snapshot_overrides = job.get_snapshot_overrides().get('config_overrides') or {}
                if snapshot_overrides:
                    crawler_config.update(snapshot_overrides)
                if job.config_overrides:
                    crawler_config.update(job.config_overrides)
                
                # Use seeds as starting URLs if provided
                if seed_urls:
                    crawler_config['start_urls'] = seed_urls
                
                # Apply job limits if set
                if job.max_pages_run:
                    crawler_config['max_pages'] = job.max_pages_run
                if job.max_pages_domain:
                    crawler_config['max_pages_domain'] = job.max_pages_domain
                if job.crawl_depth:
                    crawler_config['depth_limit'] = job.crawl_depth
                
                # Get crawler and execute
                crawler = get_crawler(source, config=crawler_config)
                results = crawler.crawl()
                
                # Accumulate results
                found = results.get('total_found', 0)
                new = results.get('new_articles', 0)
                dupes = results.get('duplicates', 0)
                errors = results.get('errors', 0)
                pages = results.get('pages_crawled', 1)
                
                total_found += found
                total_new += new
                total_duplicates += dupes
                total_errors += errors
                total_pages += pages
                
                # Update source result
                if source_result:
                    source_result.status = 'completed'
                    source_result.completed_at = timezone.now()
                    source_result.articles_found = found
                    source_result.articles_new = new
                    source_result.articles_duplicate = dupes
                    source_result.pages_crawled = pages
                    source_result.error_count = errors
                    source_result.save()
                
                # Update job progress
                job.new_articles = total_new
                job.duplicates = total_duplicates
                job.pages_crawled = total_pages
                job.errors = total_errors
                job.save()
                
                # Log progress event
                CrawlJobEvent.objects.create(
                    crawl_job=job,
                    event_type='source_complete',
                    severity='info',
                    message=f'Source {source.name}: {found} found, {new} new, {dupes} duplicates',
                    details={
                        'source_id': str(source.id),
                        'source_name': source.name,
                        'found': found,
                        'new': new,
                        'duplicates': dupes,
                    }
                )
                
            except Exception as e:
                error_code, error_msg = _classify_error(e)
                logger.error(f"Error crawling {source.name}: {error_msg}")
                
                total_errors += 1
                job.errors = total_errors
                job.save()
                
                # Update source result with error
                if source_result:
                    source_result.status = 'failed'
                    source_result.completed_at = timezone.now()
                    source_result.error_code = error_code
                    source_result.error_message = error_msg
                    source_result.save()
                
                # Log error event
                CrawlJobEvent.objects.create(
                    crawl_job=job,
                    event_type='error',
                    severity='error',
                    message=f'Error crawling {source.name}: {error_msg}',
                    details={
                        'source_id': str(source.id),
                        'error_code': error_code,
                        'error_message': error_msg,
                    }
                )
        
        # Job completed successfully
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.new_articles = total_new
        job.duplicates = total_duplicates
        job.pages_crawled = total_pages
        job.errors = total_errors
        job.save()
        
        # Log completion event
        CrawlJobEvent.objects.create(
            crawl_job=job,
            event_type='complete',
            severity='info',
            message=f'Job completed: {total_found} found, {total_new} new, {total_duplicates} duplicates',
            details={
                'total_found': total_found,
                'total_new': total_new,
                'total_duplicates': total_duplicates,
                'total_errors': total_errors,
                'total_pages': total_pages,
            }
        )
        
        logger.info(f"Job {job_id} completed: {total_found} found, {total_new} new")
        
        return {
            'success': True,
            'status': 'completed',
            'total_found': total_found,
            'total_new': total_new,
            'total_duplicates': total_duplicates,
            'total_errors': total_errors,
            'total_pages': total_pages,
        }
        
    except Exception as e:
        error_code, error_msg = _classify_error(e)
        logger.exception(f"Job {job_id} failed: {error_msg}")
        
        # Mark job as failed
        job.status = 'failed'
        job.completed_at = timezone.now()
        job.error_message = error_msg
        job.save()
        
        # Log failure event
        CrawlJobEvent.objects.create(
            crawl_job=job,
            event_type='fail',
            severity='error',
            message=f'Job failed: {error_msg}',
            details={
                'error_code': error_code,
                'error_message': error_msg,
            }
        )
        
        should_retry, max_attempts, countdown = _get_retry_decision(error_code, self.request.retries)
        attempt_number = self.request.retries + 1

        if should_retry and countdown is not None:
            logger.info(
                f"Retrying run_crawl_job {job_id} in {countdown}s "
                f"(attempt {attempt_number + 1}/{max_attempts}, error_code={error_code})"
            )
            raise self.retry(exc=e, countdown=countdown)

        logger.info(
            f"Not retrying run_crawl_job {job_id} "
            f"(attempt {attempt_number}/{max_attempts}, error_code={error_code})"
        )
        return {
            'success': False,
            'status': 'failed',
            'error_code': error_code,
            'error_message': error_msg,
        }
