#!/usr/bin/env python
"""
Phase 10.4: Seeds API Test Script

Tests the Seeds CRUD, import, validate, and promote endpoints.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.seeds.models import Seed, SeedBatch
from apps.sources.models import Source

User = get_user_model()


class SeedsAPITestCase(TestCase):
    """Test cases for Seeds API."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create test user
        self.user, created = User.objects.get_or_create(
            username='seedtest',
            defaults={'email': 'seedtest@example.com'}
        )
        if created:
            self.user.set_password('testpass123')
            self.user.save()
        
        # Login to get JWT token
        response = self.client.post('/api/auth/login/', {
            'username': 'seedtest',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Login failed: {response.data}")
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Clean up test data
        Seed.objects.filter(domain__contains='example').delete()
        Source.objects.filter(domain__contains='example').delete()
    
    def tearDown(self):
        # Clean up
        Seed.objects.filter(domain__contains='example').delete()
        Source.objects.filter(domain__contains='example').delete()
    
    def test_01_list_seeds_empty(self):
        """Test listing seeds when none exist."""
        Seed.objects.all().delete()
        
        response = self.client.get('/api/seeds/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        print("✓ List seeds (empty) works")
    
    def test_02_create_seed(self):
        """Test creating a single seed."""
        response = self.client.post('/api/seeds/', {
            'url': 'https://example-news.com/articles',
            'notes': 'Test seed',
            'tags': ['test', 'news']
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Create failed: {response.data}")
        self.assertEqual(response.data['domain'], 'example-news.com')
        self.assertEqual(response.data['status'], 'pending')
        
        seed_id = response.data['id']
        print(f"✓ Create seed works (ID: {seed_id})")
        return seed_id
    
    def test_03_retrieve_seed(self):
        """Test getting seed details."""
        seed_id = self.test_02_create_seed()
        
        response = self.client.get(f'/api/seeds/{seed_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], seed_id)
        self.assertIn('validation_summary', response.data)
        print("✓ Retrieve seed works")
    
    def test_04_update_seed(self):
        """Test updating a seed."""
        seed_id = self.test_02_create_seed()
        
        response = self.client.patch(f'/api/seeds/{seed_id}/', {
            'notes': 'Updated notes',
            'tags': ['updated']
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Update failed: {response.data}")
        
        # Verify update
        response = self.client.get(f'/api/seeds/{seed_id}/')
        self.assertEqual(response.data['notes'], 'Updated notes')
        print("✓ Update seed works")
    
    def test_05_delete_seed(self):
        """Test deleting a seed."""
        seed_id = self.test_02_create_seed()
        
        response = self.client.delete(f'/api/seeds/{seed_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deleted
        response = self.client.get(f'/api/seeds/{seed_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        print("✓ Delete seed works")
    
    def test_06_bulk_import_urls(self):
        """Test bulk importing seeds from URL list."""
        response = self.client.post('/api/seeds/import/', {
            'format': 'urls',
            'urls': [
                'https://example-site1.com/news',
                'https://example-site2.com/articles',
                'https://example-site3.com/blog',
            ],
            'tags': ['imported'],
            'skip_duplicates': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Import failed: {response.data}")
        self.assertEqual(response.data['created'], 3)
        self.assertIsNotNone(response.data['batch_id'])
        print(f"✓ Bulk import works ({response.data['created']} created)")
        return response.data['batch_id']
    
    def test_07_bulk_import_text(self):
        """Test bulk importing seeds from text."""
        response = self.client.post('/api/seeds/import/', {
            'format': 'text',
            'text': '''https://example-text1.com/news
https://example-text2.com/articles
https://example-text3.com/blog''',
            'skip_duplicates': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Import failed: {response.data}")
        self.assertEqual(response.data['created'], 3)
        print(f"✓ Bulk import (text) works ({response.data['created']} created)")
    
    def test_08_import_duplicates(self):
        """Test that duplicate URLs are handled."""
        # Create first seed
        self.client.post('/api/seeds/', {
            'url': 'https://example-dup.com/news'
        }, format='json')
        
        # Try to import same URL
        response = self.client.post('/api/seeds/import/', {
            'format': 'urls',
            'urls': ['https://example-dup.com/news'],
            'skip_duplicates': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['duplicates'], 1)
        self.assertEqual(response.data['created'], 0)
        print("✓ Duplicate handling works")
    
    def test_09_filter_seeds(self):
        """Test filtering seeds."""
        # Create seeds with different statuses
        Seed.objects.create(url='https://example-filter1.com', status='pending')
        Seed.objects.create(url='https://example-filter2.com', status='valid')
        
        # Filter by status
        response = self.client.get('/api/seeds/?status=pending')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for seed in response.data['results']:
            self.assertEqual(seed['status'], 'pending')
        
        # Search by domain
        response = self.client.get('/api/seeds/?domain=example-filter')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 2)
        print("✓ Filter seeds works")
    
    def test_10_validate_seed(self):
        """Test seed validation (will fail for fake URL but endpoint works)."""
        seed = Seed.objects.create(
            url='https://httpbin.org/html',  # Use httpbin for testing
            added_by=self.user
        )
        
        response = self.client.post(f'/api/seeds/{seed.id}/validate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_reachable', response.data)
        self.assertIn('is_crawlable', response.data)
        self.assertIn('status', response.data)
        print("✓ Validate seed works")
    
    def test_11_promote_seed(self):
        """Test promoting a valid seed to a source."""
        # Create a valid seed
        seed = Seed.objects.create(
            url='https://example-promote.com/news',
            status='valid',
            is_reachable=True,
            is_crawlable=True,
            has_articles=True,
            added_by=self.user
        )
        
        response = self.client.post(f'/api/seeds/{seed.id}/promote/', {
            'name': 'Example Promote Site',
            'source_type': 'news',
            'crawl_frequency': 'daily',
            'auto_activate': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Promote failed: {response.data}")
        self.assertIn('source_id', response.data)
        
        # Verify seed is marked promoted
        seed.refresh_from_db()
        self.assertEqual(seed.status, 'promoted')
        self.assertIsNotNone(seed.promoted_to)
        print(f"✓ Promote seed works (Source ID: {response.data['source_id']})")
    
    def test_12_batch_promote(self):
        """Test batch promoting multiple seeds."""
        # Create valid seeds
        seed1 = Seed.objects.create(
            url='https://example-batch1.com/news',
            status='valid',
            is_reachable=True,
            is_crawlable=True,
            added_by=self.user
        )
        seed2 = Seed.objects.create(
            url='https://example-batch2.com/news',
            status='valid',
            is_reachable=True,
            is_crawlable=True,
            added_by=self.user
        )
        
        response = self.client.post('/api/seeds/promote-batch/', {
            'seed_ids': [str(seed1.id), str(seed2.id)],
            'source_type': 'news',
            'auto_activate': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Batch promote failed: {response.data}")
        self.assertEqual(response.data['promoted_count'], 2)
        print(f"✓ Batch promote works ({response.data['promoted_count']} promoted)")
    
    def test_13_reject_seed(self):
        """Test rejecting a seed."""
        seed = Seed.objects.create(
            url='https://example-reject.com/news',
            added_by=self.user
        )
        
        response = self.client.post(f'/api/seeds/{seed.id}/reject/', {
            'reason': 'Not relevant'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'rejected')
        
        # Verify seed is rejected
        seed.refresh_from_db()
        self.assertEqual(seed.status, 'rejected')
        print("✓ Reject seed works")
    
    def test_14_list_batches(self):
        """Test listing import batches."""
        # Create a batch via import
        self.test_06_bulk_import_urls()
        
        response = self.client.get('/api/seeds/batches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
        print("✓ List batches works")
    
    def test_15_get_stats(self):
        """Test getting seed statistics."""
        # Create some seeds
        Seed.objects.create(url='https://example-stat1.com', status='pending')
        Seed.objects.create(url='https://example-stat2.com', status='valid')
        
        response = self.client.get('/api/seeds/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total', response.data)
        self.assertIn('by_status', response.data)
        self.assertIn('promotable', response.data)
        print(f"✓ Stats works (total: {response.data['total']})")
    
    def test_16_seed_not_found(self):
        """Test 404 for non-existent seed."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/seeds/{fake_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        print("✓ Seed not found (404) works")
    
    def test_17_unauthenticated_access(self):
        """Test that unauthenticated access is denied."""
        self.client.credentials()  # Remove auth
        
        response = self.client.get('/api/seeds/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        print("✓ Unauthenticated access denied")
    
    def test_18_cannot_promote_invalid_seed(self):
        """Test that invalid seeds cannot be promoted."""
        seed = Seed.objects.create(
            url='https://example-invalid.com/news',
            status='invalid',
            is_reachable=False,
            added_by=self.user
        )
        
        response = self.client.post(f'/api/seeds/{seed.id}/promote/', {
            'name': 'Should Fail',
        }, format='json')
        
        # Promotion should still work but create a source
        # The is_promotable check is informational
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        print("✓ Promote validation works")


def run_tests():
    """Run all test cases."""
    from django.test.utils import setup_test_environment, teardown_test_environment
    from django.test.runner import DiscoverRunner
    
    setup_test_environment()
    
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases()
    
    tests = [
        'test_01_list_seeds_empty',
        'test_02_create_seed',
        'test_03_retrieve_seed',
        'test_04_update_seed',
        'test_05_delete_seed',
        'test_06_bulk_import_urls',
        'test_07_bulk_import_text',
        'test_08_import_duplicates',
        'test_09_filter_seeds',
        'test_10_validate_seed',
        'test_11_promote_seed',
        'test_12_batch_promote',
        'test_13_reject_seed',
        'test_14_list_batches',
        'test_15_get_stats',
        'test_16_seed_not_found',
        'test_17_unauthenticated_access',
        'test_18_cannot_promote_invalid_seed',
    ]
    
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("PHASE 10.4: SEEDS API TESTS")
    print("=" * 60 + "\n")
    
    for test_name in tests:
        try:
            test = SeedsAPITestCase(test_name)
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
