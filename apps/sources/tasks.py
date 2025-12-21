"""
Celery tasks for source crawling.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def crawl_source(self, source_id):
    """
    Crawl a single source asynchronously.

    Args:
        source_id: UUID of the source to crawl

    Returns:
        dict with crawl results
    """
    from apps.sources.models import Source, CrawlJob
    from apps.sources.crawlers import get_crawler

    try:
        # Get the source
        source = Source.objects.get(id=source_id)
        logger.info(f"Starting crawl task for {source.name}")

        # Create crawl job record
        crawl_job = CrawlJob.objects.create(
            source=source,
            status='pending',
            task_id=self.request.id
        )

        # Update status to running
        crawl_job.status = 'running'
        crawl_job.started_at = timezone.now()
        crawl_job.save()

        # Get crawler and execute
        crawler = get_crawler(source)
        results = crawler.crawl()

        # Update crawl job with results
        crawl_job.status = 'completed'
        crawl_job.completed_at = timezone.now()
        crawl_job.total_found = results.get('total_found', 0)
        crawl_job.new_articles = results.get('new_articles', 0)
        crawl_job.duplicates = results.get('duplicates', 0)
        crawl_job.errors = results.get('errors', 0)
        crawl_job.save()

        logger.info(
            f"Crawl complete for {source.name}: "
            f"{results['new_articles']} new articles"
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

        # Update crawl job as failed
        try:
            crawl_job.status = 'failed'
            crawl_job.completed_at = timezone.now()
            crawl_job.error_message = str(exc)
            crawl_job.save()
        except:
            pass

        # Retry with exponential backoff
        raise self.retry(
            exc=exc,
            countdown=60 * (2 ** self.request.retries)
        )


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
