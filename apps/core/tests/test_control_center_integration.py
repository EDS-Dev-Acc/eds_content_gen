"""
Integration tests for Control Center orchestration flows.

Covers:
- Single- and multi-source launch lifecycle
- Pause/resume/stop transitions
- Clone and edit validation behaviors
"""

import pytest
from unittest.mock import MagicMock, patch
from django.urls import reverse

from apps.core.console_views import ControlCenterSaveView
from apps.sources.models import (
    CrawlJob,
    CrawlJobEvent,
    CrawlJobSeed,
    CrawlJobSourceResult,
    Source,
)


@pytest.fixture
def user(db, django_user_model):
    """Create a test user for authenticated console actions."""
    return django_user_model.objects.create_user(username='tester', password='pass')


@pytest.fixture
def authed_client(client, user):
    """Return an authenticated client."""
    client.force_login(user)
    return client


@pytest.fixture
def enable_celery_eager(settings):
    """Run Celery tasks eagerly for integration-style assertions."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    return settings


def create_source(name_suffix: str) -> Source:
    """Helper to create a minimal source."""
    return Source.objects.create(
        name=f"Source {name_suffix}",
        domain=f"{name_suffix}.example.com",
        url=f"https://{name_suffix}.example.com",
        crawler_type='scrapy',
    )


@pytest.mark.django_db
def test_single_source_launch_reaches_completion(authed_client, enable_celery_eager):
    """Starting a single-source run should progress queued → running → completed."""
    source = create_source('single')
    job = CrawlJob.objects.create(
        name='Single Source Run',
        source=source,
        status='draft',
        is_multi_source=False,
    )

    with patch('apps.sources.crawlers.get_crawler') as mock_get_crawler:
        crawler = MagicMock()
        crawler.crawl.return_value = {
            'total_found': 5,
            'new_articles': 3,
            'duplicates': 1,
            'pages_crawled': 2,
        }
        mock_get_crawler.return_value = crawler

        response = authed_client.post(
            reverse('console:control_center_control', args=[job.id, 'start'])
        )
        assert response.status_code == 302

    job.refresh_from_db()
    assert job.status == 'completed'
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.new_articles == 3
    assert CrawlJobEvent.objects.filter(
        crawl_job=job,
        event_type='complete',
    ).exists()


@pytest.mark.django_db
def test_multi_source_launch_updates_children_and_events(authed_client, enable_celery_eager):
    """Multi-source runs should update child results and emit completion events."""
    source_a = create_source('alpha')
    source_b = create_source('beta')
    job = CrawlJob.objects.create(
        name='Multi Source Run',
        status='draft',
        is_multi_source=True,
    )
    CrawlJobSourceResult.objects.create(crawl_job=job, source=source_a, status='pending')
    CrawlJobSourceResult.objects.create(crawl_job=job, source=source_b, status='pending')

    with patch('apps.sources.crawlers.get_crawler') as mock_get_crawler:
        crawler = MagicMock()
        crawler.crawl.return_value = {
            'total_found': 2,
            'new_articles': 1,
            'duplicates': 0,
            'pages_crawled': 1,
        }
        mock_get_crawler.return_value = crawler

        response = authed_client.post(
            reverse('console:control_center_control', args=[job.id, 'start'])
        )
        assert response.status_code == 302

    job.refresh_from_db()
    assert job.status == 'completed'
    assert job.source_results.filter(status='completed').count() == 2
    assert job.pages_crawled >= 2  # Aggregated from both sources
    assert job.events.filter(event_type='source_complete').count() == 2
    assert job.events.filter(event_type='complete').exists()


@pytest.mark.django_db
def test_pause_resume_stop_transitions_record_events(authed_client):
    """Pause/resume/stop actions should update status and log events."""
    job = CrawlJob.objects.create(
        name='Control Actions Run',
        status='running',
    )

    pause_response = authed_client.post(
        reverse('console:control_center_control', args=[job.id, 'pause'])
    )
    assert pause_response.status_code == 302
    job.refresh_from_db()
    assert job.status == 'paused'
    assert job.events.filter(event_type='paused').exists()

    resume_response = authed_client.post(
        reverse('console:control_center_control', args=[job.id, 'resume'])
    )
    assert resume_response.status_code == 302
    job.refresh_from_db()
    assert job.status == 'running'
    assert job.events.filter(event_type='resumed').exists()

    stop_response = authed_client.post(
        reverse('console:control_center_control', args=[job.id, 'stop'])
    )
    assert stop_response.status_code == 302
    job.refresh_from_db()
    assert job.status == 'stopped'
    assert job.events.filter(event_type='stopped').exists()


@pytest.mark.django_db
def test_clone_preserves_sources_and_seeds(authed_client):
    """Cloning should create a draft with the same sources and seeds."""
    primary_source = create_source('primary')
    secondary_source = create_source('secondary')
    original = CrawlJob.objects.create(
        name='Original Run',
        source=primary_source,
        status='draft',
        is_multi_source=True,
    )
    CrawlJobSourceResult.objects.create(crawl_job=original, source=primary_source)
    CrawlJobSourceResult.objects.create(crawl_job=original, source=secondary_source)
    CrawlJobSeed.objects.create(
        crawl_job=original,
        url='https://seed.example.com',
        label='Seed A',
        max_pages=5,
        crawl_depth=2,
        fetch_mode='http',
        proxy_group='default',
    )

    response = authed_client.post(
        reverse('console:control_center_clone', args=[original.id])
    )
    assert response.status_code == 302

    clone = CrawlJob.objects.exclude(id=original.id).get()
    assert clone.status == 'draft'
    assert clone.is_multi_source is True
    assert set(clone.source_results.values_list('source_id', flat=True)) == {
        primary_source.id,
        secondary_source.id,
    }
    clone_seed = clone.job_seeds.get()
    assert clone_seed.url == 'https://seed.example.com'
    assert clone_seed.label == 'Seed A'
    assert clone_seed.max_pages == 5
    assert clone_seed.crawl_depth == 2
    assert clone_seed.fetch_mode == 'http'
    assert clone_seed.proxy_group == 'default'


@pytest.mark.django_db
def test_launch_validation_blocks_missing_sources(rf, user):
    """Edit/run validation should surface blocking errors for empty multi-source runs."""
    job = CrawlJob.objects.create(
        name='Invalid Multi Run',
        status='draft',
        is_multi_source=True,
    )
    request = rf.post('/console/control-center/save/', {'action': 'run'})
    request.user = user
    view = ControlCenterSaveView()

    response = view._launch_job(request, job)

    content = response.content.decode()
    assert 'Cannot launch' in content
    assert 'Select at least one source or seed' in content
