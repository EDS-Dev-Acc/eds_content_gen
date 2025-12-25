#!/usr/bin/env python
"""
Phase 10.2 - Runs API Tests

Tests for CrawlJob (Run) endpoints.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.sources.models import Source, CrawlJob, CrawlJobSourceResult

User = get_user_model()


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, name, test_func):
        """Run a single test."""
        try:
            test_func()
            self.passed += 1
            print(f"  [PASS] {name}")
        except AssertionError as e:
            self.failed += 1
            self.errors.append((name, str(e)))
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            self.failed += 1
            self.errors.append((name, str(e)))
            print(f"  [ERROR] {name}: {e}")

    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        if self.errors:
            print("\nFailures:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


def cleanup():
    """Clean up test data."""
    User.objects.filter(username__startswith='testuser_runs_').delete()
    Source.objects.filter(name__startswith='Test Source Runs').delete()
    CrawlJob.objects.filter(error_message__startswith='Test run').delete()


def get_auth_client():
    """Get authenticated API client."""
    user, _ = User.objects.get_or_create(
        username='testuser_runs_1',
        defaults={'email': 'runs@test.com'}
    )
    user.set_password('testpass123')
    user.save()
    
    client = APIClient()
    response = client.post('/api/auth/login/', {
        'username': 'testuser_runs_1',
        'password': 'testpass123'
    })
    tokens = response.json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client, user


def create_test_source(name_suffix='1'):
    """Create a test source."""
    source, _ = Source.objects.get_or_create(
        domain=f'testrunssource{name_suffix}.com',
        defaults={
            'name': f'Test Source Runs {name_suffix}',
            'url': f'https://testrunssource{name_suffix}.com',
            'source_type': 'news_site',
            'status': 'active',
            'reputation_score': 75,
        }
    )
    return source


# =============================================================================
# Model Tests
# =============================================================================

def test_crawljob_extended_fields():
    """Test CrawlJob has new Phase 10.2 fields."""
    cleanup()
    source = create_test_source('model1')
    
    job = CrawlJob.objects.create(
        source=source,
        status='pending',
        priority=7,
        triggered_by='api',
        config_overrides={'max_pages': 5},
        is_multi_source=False,
    )
    
    assert job.priority == 7
    assert job.triggered_by == 'api'
    assert job.config_overrides['max_pages'] == 5
    assert job.is_multi_source == False
    
    job.delete()


def test_crawljob_source_result():
    """Test CrawlJobSourceResult model."""
    cleanup()
    source = create_test_source('model2')
    
    # Create parent job
    parent_job = CrawlJob.objects.create(
        source=None,
        status='running',
        is_multi_source=True,
    )
    
    # Create source result
    result = CrawlJobSourceResult.objects.create(
        crawl_job=parent_job,
        source=source,
        status='completed',
        articles_found=10,
        articles_new=5,
    )
    
    assert result.crawl_job == parent_job
    assert result.source == source
    assert result.articles_found == 10
    
    # Test relationship
    assert parent_job.source_results.count() == 1
    
    parent_job.delete()  # Cascades to result


def test_crawljob_duration_property():
    """Test duration calculation."""
    cleanup()
    source = create_test_source('model3')
    
    start = timezone.now()
    end = start + timezone.timedelta(seconds=120)
    
    job = CrawlJob.objects.create(
        source=source,
        status='completed',
        started_at=start,
        completed_at=end,
    )
    
    assert job.duration is not None
    assert job.duration_seconds == 120.0
    
    job.delete()


# =============================================================================
# API Tests
# =============================================================================

def test_list_runs():
    """Test GET /api/sources/runs/."""
    cleanup()
    client, user = get_auth_client()
    source = create_test_source('api1')
    
    # Create a run
    CrawlJob.objects.create(
        source=source,
        status='completed',
        triggered_by='manual',
        triggered_by_user=user,
        new_articles=5,
    )
    
    response = client.get('/api/sources/runs/')
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert 'results' in data
    assert len(data['results']) >= 1


def test_list_runs_filter_by_status():
    """Test filtering runs by status."""
    cleanup()
    client, user = get_auth_client()
    source = create_test_source('api2')
    
    # Create completed and pending jobs
    CrawlJob.objects.create(source=source, status='completed')
    CrawlJob.objects.create(source=source, status='pending')
    
    response = client.get('/api/sources/runs/?status=completed')
    
    assert response.status_code == 200
    data = response.json()
    for run in data['results']:
        assert run['status'] == 'completed'


def test_get_run_detail():
    """Test GET /api/sources/runs/{id}/."""
    cleanup()
    client, _ = get_auth_client()
    source = create_test_source('api3')
    
    job = CrawlJob.objects.create(
        source=source,
        status='completed',
        new_articles=10,
        total_found=15,
        config_overrides={'max_pages': 3},
    )
    
    response = client.get(f'/api/sources/runs/{job.id}/')
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data['id'] == str(job.id)
    assert data['new_articles'] == 10
    assert data['config_overrides']['max_pages'] == 3


def test_run_detail_with_source_results():
    """Test run detail includes source results for multi-source."""
    cleanup()
    client, _ = get_auth_client()
    source1 = create_test_source('api4a')
    source2 = create_test_source('api4b')
    
    # Create multi-source run
    parent_job = CrawlJob.objects.create(
        source=None,
        status='completed',
        is_multi_source=True,
    )
    
    CrawlJobSourceResult.objects.create(
        crawl_job=parent_job,
        source=source1,
        status='completed',
        articles_new=5,
    )
    CrawlJobSourceResult.objects.create(
        crawl_job=parent_job,
        source=source2,
        status='completed',
        articles_new=3,
    )
    
    response = client.get(f'/api/sources/runs/{parent_job.id}/')
    
    assert response.status_code == 200
    data = response.json()
    assert data['is_multi_source'] == True
    assert len(data['source_results']) == 2


def test_start_run_single_source():
    """Test POST /api/sources/runs/start/ with single source."""
    cleanup()
    client, _ = get_auth_client()
    source = create_test_source('api5')
    
    # Note: This will try to actually queue a task, but we're testing the API
    # The task will fail because there's no worker, but the job should be created
    response = client.post('/api/sources/runs/start/', {
        'source_ids': [str(source.id)],
        'priority': 7,
    }, format='json')
    
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"
    data = response.json()
    assert 'run_id' in data
    assert data['is_multi_source'] == False
    assert data['source_count'] == 1


def test_start_run_multi_source():
    """Test POST /api/sources/runs/start/ with multiple sources."""
    cleanup()
    client, _ = get_auth_client()
    source1 = create_test_source('api6a')
    source2 = create_test_source('api6b')
    
    response = client.post('/api/sources/runs/start/', {
        'source_ids': [str(source1.id), str(source2.id)],
        'priority': 5,
        'config_overrides': {'max_pages': 2},
    }, format='json')
    
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"
    data = response.json()
    assert data['is_multi_source'] == True
    assert data['source_count'] == 2


def test_start_run_invalid_source():
    """Test starting run with non-existent source."""
    cleanup()
    client, _ = get_auth_client()
    
    import uuid
    fake_id = str(uuid.uuid4())
    
    response = client.post('/api/sources/runs/start/', {
        'source_ids': [fake_id],
    }, format='json')
    
    assert response.status_code == 400
    data = response.json()
    assert 'source_ids' in data


def test_start_run_inactive_source():
    """Test starting run with inactive source."""
    cleanup()
    client, _ = get_auth_client()
    
    source = create_test_source('api7')
    source.status = 'paused'
    source.save()
    
    response = client.post('/api/sources/runs/start/', {
        'source_ids': [str(source.id)],
    }, format='json')
    
    assert response.status_code == 400


def test_cancel_run():
    """Test POST /api/sources/runs/{id}/cancel/."""
    cleanup()
    client, user = get_auth_client()
    source = create_test_source('api8')
    
    job = CrawlJob.objects.create(
        source=source,
        status='running',
        triggered_by_user=user,
    )
    
    response = client.post(f'/api/sources/runs/{job.id}/cancel/', {
        'reason': 'Testing cancellation'
    }, format='json')
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data['status'] == 'cancelled'
    
    job.refresh_from_db()
    assert job.status == 'cancelled'
    assert 'Testing cancellation' in job.error_message


def test_cancel_completed_run_fails():
    """Test that cancelling a completed run fails."""
    cleanup()
    client, _ = get_auth_client()
    source = create_test_source('api9')
    
    job = CrawlJob.objects.create(
        source=source,
        status='completed',
    )
    
    response = client.post(f'/api/sources/runs/{job.id}/cancel/')
    
    assert response.status_code == 400


def test_list_sources():
    """Test GET /api/sources/."""
    cleanup()
    client, _ = get_auth_client()
    source = create_test_source('api10')
    
    response = client.get('/api/sources/')
    
    assert response.status_code == 200
    data = response.json()
    assert 'results' in data


def test_runs_require_auth():
    """Test that runs endpoints require authentication."""
    client = APIClient()  # No auth
    
    response = client.get('/api/sources/runs/')
    assert response.status_code == 401


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all tests."""
    print("="*60)
    print("Phase 10.2 - Runs API Tests")
    print("="*60)
    
    runner = TestRunner()
    
    print("\n[Model Tests]")
    runner.run_test("CrawlJob extended fields", test_crawljob_extended_fields)
    runner.run_test("CrawlJobSourceResult model", test_crawljob_source_result)
    runner.run_test("CrawlJob duration property", test_crawljob_duration_property)
    
    print("\n[API Tests]")
    runner.run_test("List runs", test_list_runs)
    runner.run_test("Filter runs by status", test_list_runs_filter_by_status)
    runner.run_test("Get run detail", test_get_run_detail)
    runner.run_test("Run detail with source results", test_run_detail_with_source_results)
    runner.run_test("Start run single source", test_start_run_single_source)
    runner.run_test("Start run multi-source", test_start_run_multi_source)
    runner.run_test("Start run invalid source", test_start_run_invalid_source)
    runner.run_test("Start run inactive source", test_start_run_inactive_source)
    runner.run_test("Cancel run", test_cancel_run)
    runner.run_test("Cancel completed run fails", test_cancel_completed_run_fails)
    runner.run_test("List sources", test_list_sources)
    runner.run_test("Runs require auth", test_runs_require_auth)
    
    success = runner.summary()
    
    if success:
        print("\n[SUCCESS] All Phase 10.2 tests passed!")
    else:
        print("\n[FAILURE] Some tests failed")
    
    # Final cleanup
    cleanup()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
