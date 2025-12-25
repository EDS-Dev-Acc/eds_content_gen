#!/usr/bin/env python
"""
Phase 10.3: Schedules API Test Script

Tests the django-celery-beat based Schedules API endpoints.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule

User = get_user_model()


class SchedulesAPITestCase(TestCase):
    """Test cases for Schedules API."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create test user (must be in setUp, not setUpClass for test DB)
        self.user, created = User.objects.get_or_create(
            username='scheduletest',
            defaults={
                'email': 'scheduletest@example.com',
            }
        )
        if created:
            self.user.set_password('testpass123')
            self.user.save()
        
        # Login to get JWT token
        response = self.client.post('/api/auth/login/', {
            'username': 'scheduletest',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Login failed: {response.data}")
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Clean up any existing test schedules
        PeriodicTask.objects.filter(name__startswith='Test Schedule').delete()
    
    def tearDown(self):
        # Clean up test schedules
        PeriodicTask.objects.filter(name__startswith='Test Schedule').delete()
    
    def test_01_list_schedules_empty(self):
        """Test listing schedules when none exist."""
        # First delete all schedules
        PeriodicTask.objects.all().delete()
        
        response = self.client.get('/api/sources/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        print("✓ List schedules (empty) works")
    
    def test_02_create_interval_schedule(self):
        """Test creating an interval-based schedule."""
        response = self.client.post('/api/sources/schedules/', {
            'name': 'Test Schedule Hourly',
            'description': 'Crawl every hour',
            'task': 'apps.sources.tasks.crawl_all_active_sources',
            'schedule_type': 'interval',
            'interval': {
                'every': 1,
                'period': 'hours'
            },
            'enabled': True,
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Create failed: {response.data}")
        self.assertEqual(response.data['name'], 'Test Schedule Hourly')
        self.assertEqual(response.data['enabled'], True)
        self.assertEqual(response.data['schedule_type'], 'interval')
        self.assertIn('Every 1 hour', response.data['schedule_display'])
        
        self.schedule_id = response.data['id']
        print(f"✓ Create interval schedule works (ID: {self.schedule_id})")
        return response.data['id']
    
    def test_03_create_crontab_schedule(self):
        """Test creating a crontab-based schedule."""
        response = self.client.post('/api/sources/schedules/', {
            'name': 'Test Schedule Daily',
            'description': 'Crawl at midnight',
            'task': 'apps.sources.tasks.crawl_all_active_sources',
            'schedule_type': 'crontab',
            'crontab': {
                'minute': '0',
                'hour': '0',
                'day_of_week': '*',
                'day_of_month': '*',
                'month_of_year': '*'
            },
            'enabled': False,
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Create failed: {response.data}")
        self.assertEqual(response.data['name'], 'Test Schedule Daily')
        self.assertEqual(response.data['schedule_type'], 'crontab')
        self.assertEqual(response.data['enabled'], False)
        print(f"✓ Create crontab schedule works (ID: {response.data['id']})")
        return response.data['id']
    
    def test_04_list_schedules_with_data(self):
        """Test listing schedules after creating some."""
        # Create schedules first
        self.test_02_create_interval_schedule()
        self.test_03_create_crontab_schedule()
        
        response = self.client.get('/api/sources/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
        print(f"✓ List schedules works ({len(response.data)} schedules)")
    
    def test_05_retrieve_schedule(self):
        """Test getting schedule details."""
        schedule_id = self.test_02_create_interval_schedule()
        
        response = self.client.get(f'/api/sources/schedules/{schedule_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], schedule_id)
        self.assertEqual(response.data['name'], 'Test Schedule Hourly')
        self.assertIn('interval', response.data)
        print(f"✓ Retrieve schedule works")
    
    def test_06_update_schedule(self):
        """Test updating a schedule."""
        schedule_id = self.test_02_create_interval_schedule()
        
        response = self.client.put(f'/api/sources/schedules/{schedule_id}/', {
            'name': 'Test Schedule Updated',
            'description': 'Updated description',
            'enabled': False,
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Update failed: {response.data}")
        self.assertEqual(response.data['name'], 'Test Schedule Updated')
        self.assertEqual(response.data['description'], 'Updated description')
        self.assertEqual(response.data['enabled'], False)
        print("✓ Update schedule works")
    
    def test_07_toggle_schedule(self):
        """Test toggling schedule enabled state."""
        schedule_id = self.test_02_create_interval_schedule()
        
        # Disable
        response = self.client.post(f'/api/sources/schedules/{schedule_id}/toggle/', {
            'enabled': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['enabled'], False)
        
        # Enable
        response = self.client.post(f'/api/sources/schedules/{schedule_id}/toggle/', {
            'enabled': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['enabled'], True)
        print("✓ Toggle schedule works")
    
    def test_08_filter_schedules_by_enabled(self):
        """Test filtering schedules by enabled status."""
        # Create both enabled and disabled schedules
        self.test_02_create_interval_schedule()  # enabled=True
        self.test_03_create_crontab_schedule()   # enabled=False
        
        # Filter enabled only
        response = self.client.get('/api/sources/schedules/?enabled=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for schedule in response.data:
            self.assertTrue(schedule['enabled'])
        
        # Filter disabled only
        response = self.client.get('/api/sources/schedules/?enabled=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for schedule in response.data:
            self.assertFalse(schedule['enabled'])
        
        print("✓ Filter schedules by enabled works")
    
    def test_09_pause_all_schedules(self):
        """Test pausing all schedules."""
        # Create some enabled schedules
        self.test_02_create_interval_schedule()
        self.test_03_create_crontab_schedule()
        
        # Enable all first
        PeriodicTask.objects.filter(name__startswith='Test Schedule').update(enabled=True)
        
        # Pause all
        response = self.client.post('/api/sources/schedules/pause-all/', {
            'action': 'pause'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['action'], 'paused')
        
        # Verify all disabled
        enabled_count = PeriodicTask.objects.filter(
            name__startswith='Test Schedule',
            enabled=True
        ).count()
        self.assertEqual(enabled_count, 0)
        print("✓ Pause all schedules works")
    
    def test_10_resume_all_schedules(self):
        """Test resuming all schedules."""
        # Create some disabled schedules
        self.test_02_create_interval_schedule()
        self.test_03_create_crontab_schedule()
        
        # Disable all first
        PeriodicTask.objects.filter(name__startswith='Test Schedule').update(enabled=False)
        
        # Resume all
        response = self.client.post('/api/sources/schedules/pause-all/', {
            'action': 'resume'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['action'], 'resumed')
        print("✓ Resume all schedules works")
    
    def test_11_bulk_enable_disable(self):
        """Test bulk enable/disable."""
        id1 = self.test_02_create_interval_schedule()
        id2 = self.test_03_create_crontab_schedule()
        
        # Bulk disable
        response = self.client.post('/api/sources/schedules/bulk/', {
            'schedule_ids': [id1, id2],
            'action': 'disable'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['action'], 'disable')
        
        # Verify
        task1 = PeriodicTask.objects.get(pk=id1)
        task2 = PeriodicTask.objects.get(pk=id2)
        self.assertFalse(task1.enabled)
        self.assertFalse(task2.enabled)
        print("✓ Bulk disable schedules works")
    
    def test_12_delete_schedule(self):
        """Test deleting a schedule."""
        schedule_id = self.test_02_create_interval_schedule()
        
        response = self.client.delete(f'/api/sources/schedules/{schedule_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deleted
        self.assertFalse(PeriodicTask.objects.filter(pk=schedule_id).exists())
        print("✓ Delete schedule works")
    
    def test_13_create_schedule_validation(self):
        """Test schedule creation validation."""
        # Missing interval settings for interval type
        response = self.client.post('/api/sources/schedules/', {
            'name': 'Test Schedule Invalid',
            'task': 'apps.sources.tasks.crawl_all_active_sources',
            'schedule_type': 'interval',
            # Missing interval!
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        print("✓ Create schedule validation works")
    
    def test_14_schedule_not_found(self):
        """Test 404 for non-existent schedule."""
        response = self.client.get('/api/sources/schedules/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        print("✓ Schedule not found (404) works")
    
    def test_15_unauthenticated_access(self):
        """Test that unauthenticated access is denied."""
        self.client.credentials()  # Remove auth
        
        response = self.client.get('/api/sources/schedules/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        print("✓ Unauthenticated access denied")


def run_tests():
    """Run all test cases."""
    from django.test.utils import setup_test_environment, teardown_test_environment
    from django.test.runner import DiscoverRunner
    
    setup_test_environment()
    
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases()
    
    test_case = SchedulesAPITestCase('test_01_list_schedules_empty')
    
    tests = [
        'test_01_list_schedules_empty',
        'test_02_create_interval_schedule',
        'test_03_create_crontab_schedule',
        'test_04_list_schedules_with_data',
        'test_05_retrieve_schedule',
        'test_06_update_schedule',
        'test_07_toggle_schedule',
        'test_08_filter_schedules_by_enabled',
        'test_09_pause_all_schedules',
        'test_10_resume_all_schedules',
        'test_11_bulk_enable_disable',
        'test_12_delete_schedule',
        'test_13_create_schedule_validation',
        'test_14_schedule_not_found',
        'test_15_unauthenticated_access',
    ]
    
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("PHASE 10.3: SCHEDULES API TESTS")
    print("=" * 60 + "\n")
    
    for test_name in tests:
        try:
            test = SchedulesAPITestCase(test_name)
            test.setUp()
            getattr(test, test_name)()
            test.tearDown()
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            failed += 1
    
    runner.teardown_databases(old_config)
    teardown_test_environment()
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
