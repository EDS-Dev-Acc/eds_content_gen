#!/usr/bin/env python
"""
Test script for Article Viewer API (Phase 10.5).

Tests all 7 tab endpoints plus list/detail/stats.

Usage:
    python scripts/test_article_viewer.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status as http_status

from apps.sources.models import Source
from apps.articles.models import (
    Article,
    ArticleRawCapture,
    ArticleScoreBreakdown,
    ArticleLLMArtifact,
    ArticleImage,
)

User = get_user_model()


class ArticleViewerAPITestCase(TestCase):
    """Test Article Viewer API endpoints."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all tests."""
        # Create user
        cls.user = User.objects.create_user(
            username='articleviewer',
            email='articleviewer@test.com',
            password='testpass123'
        )
        
        # Create source
        cls.source = Source.objects.create(
            name='Test News Source',
            domain='testnews.example.com',
            url='https://testnews.example.com',
            source_type='news_site',
            reputation_score=75,
            status='active',
            crawl_frequency_hours=24
        )
        
        # Create articles with different statuses/scores
        cls.article1 = Article.objects.create(
            source=cls.source,
            url='https://testnews.example.com/article-1',
            title='High Quality Article',
            author='John Doe',
            raw_html='<html><body><h1>Test Article</h1><p>Content here</p></body></html>',
            extracted_text='Test Article\n\nContent here',
            word_count=10,
            processing_status='completed',
            primary_topic='energy',
            primary_region='north_america',
            reputation_score=80,
            recency_score=90,
            topic_alignment_score=75,
            content_quality_score=85,
            geographic_relevance_score=70,
            ai_penalty=0,
            total_score=80,
            ai_content_detected=False,
            ai_confidence_score=0.1,
        )
        
        cls.article2 = Article.objects.create(
            source=cls.source,
            url='https://testnews.example.com/article-2',
            title='Medium Quality Article',
            processing_status='analyzed',
            primary_topic='oil',
            total_score=55,
        )
        
        cls.article3 = Article.objects.create(
            source=cls.source,
            url='https://testnews.example.com/article-3',
            title='Low Quality Article',
            processing_status='collected',
            total_score=25,
            ai_content_detected=True,
            ai_confidence_score=0.85,
        )
        
        cls.article4 = Article.objects.create(
            source=cls.source,
            url='https://testnews.example.com/article-4',
            title='Unscored Article',
            processing_status='collected',
            total_score=0,
        )
        
        # Create raw capture for article1
        cls.raw_capture = ArticleRawCapture.objects.create(
            article=cls.article1,
            http_status=200,
            response_headers={'Content-Type': 'text/html; charset=utf-8'},
            request_headers={'User-Agent': 'TestBot/1.0'},
            fetch_method='requests',
            fetch_duration_ms=150,
            content_type='text/html',
            content_length=1024,
            final_url='https://testnews.example.com/article-1',
        )
        
        # Create score breakdown for article1
        cls.score_breakdown = ArticleScoreBreakdown.objects.create(
            article=cls.article1,
            reputation_raw=0.8,
            reputation_weighted=32.0,
            reputation_reasoning='Established source with good track record',
            recency_raw=0.9,
            recency_weighted=18.0,
            recency_reasoning='Published within last 24 hours',
            topic_raw=0.75,
            topic_weighted=15.0,
            topic_reasoning='Strong alignment with energy topics',
            quality_raw=0.85,
            quality_weighted=17.0,
            quality_reasoning='Well-structured article with citations',
            geographic_raw=0.7,
            geographic_weighted=7.0,
            geographic_reasoning='Covers North American energy market',
            ai_detection_raw=0.1,
            ai_penalty_applied=0.0,
            ai_reasoning='Low probability of AI-generated content',
            scoring_version='1.0',
        )
        
        # Create LLM artifacts for article1
        cls.artifact1 = ArticleLLMArtifact.objects.create(
            article=cls.article1,
            artifact_type='content_analysis',
            prompt_name='content_analysis',
            prompt_version='1.0',
            prompt_text='Analyze the following article...',
            response_text='{"topics": ["energy", "oil"], "region": "north_america"}',
            response_parsed={'topics': ['energy', 'oil'], 'region': 'north_america'},
            input_tokens=500,
            output_tokens=100,
            total_tokens=600,
            estimated_cost=Decimal('0.000600'),
            model_name='gpt-4o-mini',
            latency_ms=1200,
            success=True,
        )
        
        cls.artifact2 = ArticleLLMArtifact.objects.create(
            article=cls.article1,
            artifact_type='ai_detection',
            prompt_name='ai_detection',
            prompt_version='2.0',
            prompt_text='Detect if the following text is AI-generated...',
            response_text='{"is_ai": false, "confidence": 0.1}',
            response_parsed={'is_ai': False, 'confidence': 0.1},
            input_tokens=400,
            output_tokens=50,
            total_tokens=450,
            estimated_cost=Decimal('0.000450'),
            model_name='gpt-4o-mini',
            latency_ms=800,
            success=True,
        )
        
        # Create images for article1
        cls.image1 = ArticleImage.objects.create(
            article=cls.article1,
            url='https://testnews.example.com/images/hero.jpg',
            alt_text='Article hero image',
            caption='Energy infrastructure',
            position=0,
            width=1200,
            height=800,
            file_size=150000,
            content_type='image/jpeg',
            is_primary=True,
            is_infographic=False,
        )
        
        cls.image2 = ArticleImage.objects.create(
            article=cls.article1,
            url='https://testnews.example.com/images/chart.png',
            alt_text='Production chart',
            caption='Oil production statistics',
            position=1,
            width=800,
            height=600,
            is_infographic=True,
        )
    
    def setUp(self):
        """Set up test client and authenticate."""
        self.client = APIClient()
        # Get JWT token
        response = self.client.post('/api/auth/login/', {
            'username': 'articleviewer',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
    
    # ========================================================================
    # Authentication Tests
    # ========================================================================
    
    def test_requires_authentication(self):
        """Test that endpoints require authentication."""
        client = APIClient()  # No auth
        response = client.get('/api/articles/')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
    
    # ========================================================================
    # List Tests
    # ========================================================================
    
    def _get_results(self, response_data):
        """Extract results from paginated or non-paginated response."""
        if isinstance(response_data, dict) and 'results' in response_data:
            return response_data['results']
        return response_data
    
    def test_list_articles(self):
        """Test listing all articles."""
        response = self.client.get('/api/articles/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = self._get_results(response.data)
        self.assertEqual(len(results), 4)
    
    def test_list_articles_filter_by_status(self):
        """Test filtering articles by status."""
        response = self.client.get('/api/articles/', {'status': 'completed'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = self._get_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'High Quality Article')
    
    def test_list_articles_filter_by_quality(self):
        """Test filtering articles by quality category."""
        # High quality
        response = self.client.get('/api/articles/', {'quality': 'high'})
        results = self._get_results(response.data)
        self.assertEqual(len(results), 1)
        
        # Medium quality
        response = self.client.get('/api/articles/', {'quality': 'medium'})
        results = self._get_results(response.data)
        self.assertEqual(len(results), 1)
        
        # Low quality
        response = self.client.get('/api/articles/', {'quality': 'low'})
        results = self._get_results(response.data)
        self.assertEqual(len(results), 1)
        
        # Unscored
        response = self.client.get('/api/articles/', {'quality': 'unscored'})
        results = self._get_results(response.data)
        self.assertEqual(len(results), 1)
    
    def test_list_articles_filter_by_ai_detected(self):
        """Test filtering articles by AI detection."""
        response = self.client.get('/api/articles/', {'ai_detected': 'true'})
        results = self._get_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Low Quality Article')
    
    # ========================================================================
    # Detail Tests
    # ========================================================================
    
    def test_article_detail(self):
        """Test getting full article detail."""
        response = self.client.get(f'/api/articles/{self.article1.id}/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'High Quality Article')
        self.assertEqual(response.data['total_score'], 80)
        self.assertIn('raw_capture', response.data)
        self.assertIn('score_breakdown', response.data)
        self.assertIn('llm_artifacts', response.data)
        self.assertIn('images', response.data)
    
    def test_article_not_found(self):
        """Test 404 for non-existent article."""
        response = self.client.get('/api/articles/99999/')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    # ========================================================================
    # Tab 1: Info Tests
    # ========================================================================
    
    def test_tab_info(self):
        """Test Tab 1: Article info endpoint."""
        response = self.client.get(f'/api/articles/{self.article1.id}/info/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'High Quality Article')
        self.assertEqual(response.data['author'], 'John Doe')
        self.assertEqual(response.data['source_name'], 'Test News Source')
        self.assertEqual(response.data['quality_category'], 'high')
        self.assertEqual(response.data['primary_topic'], 'energy')
        self.assertEqual(response.data['primary_region'], 'north_america')
    
    # ========================================================================
    # Tab 2: Raw Capture Tests
    # ========================================================================
    
    def test_tab_raw_capture_with_record(self):
        """Test Tab 2: Raw capture with capture record."""
        response = self.client.get(f'/api/articles/{self.article1.id}/raw_capture/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['has_capture_record'])
        self.assertEqual(response.data['http_status'], 200)
        self.assertEqual(response.data['fetch_method'], 'requests')
        self.assertIn('<html>', response.data['raw_html'])
    
    def test_tab_raw_capture_without_record(self):
        """Test Tab 2: Raw capture without capture record."""
        response = self.client.get(f'/api/articles/{self.article2.id}/raw_capture/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['has_capture_record'])
        self.assertIsNone(response.data['http_status'])
    
    # ========================================================================
    # Tab 3: Extracted Text Tests
    # ========================================================================
    
    def test_tab_extracted_text(self):
        """Test Tab 3: Extracted text endpoint."""
        response = self.client.get(f'/api/articles/{self.article1.id}/extracted/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('Test Article', response.data['extracted_text'])
        self.assertEqual(response.data['word_count'], 10)
    
    # ========================================================================
    # Tab 4: Scores Tests
    # ========================================================================
    
    def test_tab_scores_with_breakdown(self):
        """Test Tab 4: Scores with breakdown."""
        response = self.client.get(f'/api/articles/{self.article1.id}/scores/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_score'], 80)
        self.assertEqual(response.data['quality_category'], 'high')
        self.assertTrue(response.data['has_breakdown'])
        self.assertIsNotNone(response.data['breakdown'])
        self.assertIn('reputation_reasoning', response.data['breakdown'])
    
    def test_tab_scores_without_breakdown(self):
        """Test Tab 4: Scores without breakdown."""
        response = self.client.get(f'/api/articles/{self.article2.id}/scores/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['has_breakdown'])
        self.assertIsNone(response.data['breakdown'])
    
    # ========================================================================
    # Tab 5: LLM Artifacts Tests
    # ========================================================================
    
    def test_tab_llm_artifacts(self):
        """Test Tab 5: LLM artifacts endpoint."""
        response = self.client.get(f'/api/articles/{self.article1.id}/llm_artifacts/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 2)
        self.assertEqual(response.data['total_tokens'], 1050)  # 600 + 450
        self.assertIn('content_analysis', response.data['artifact_types'])
        self.assertIn('ai_detection', response.data['artifact_types'])
        self.assertEqual(len(response.data['artifacts']), 2)
    
    def test_llm_artifact_detail(self):
        """Test LLM artifact detail endpoint."""
        response = self.client.get(f'/api/articles/llm_artifacts/{self.artifact1.id}/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['artifact_type'], 'content_analysis')
        self.assertIn('prompt_text', response.data)
        self.assertIn('response_text', response.data)
        self.assertIn('response_parsed', response.data)
    
    def test_llm_artifact_not_found(self):
        """Test 404 for non-existent LLM artifact."""
        response = self.client.get('/api/articles/llm_artifacts/99999/')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    # ========================================================================
    # Tab 6: Images Tests
    # ========================================================================
    
    def test_tab_images(self):
        """Test Tab 6: Images endpoint."""
        response = self.client.get(f'/api/articles/{self.article1.id}/images/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 2)
        self.assertTrue(response.data['has_primary'])
        self.assertEqual(response.data['infographics_count'], 1)
        self.assertEqual(len(response.data['images']), 2)
    
    def test_tab_images_empty(self):
        """Test Tab 6: Images for article without images."""
        response = self.client.get(f'/api/articles/{self.article2.id}/images/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 0)
        self.assertFalse(response.data['has_primary'])
        self.assertEqual(len(response.data['images']), 0)
    
    # ========================================================================
    # Tab 7: Usage Tests
    # ========================================================================
    
    def test_tab_usage(self):
        """Test Tab 7: Usage endpoint."""
        response = self.client.get(f'/api/articles/{self.article1.id}/usage/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['used_in_content'])
        self.assertEqual(response.data['usage_count'], 0)
        self.assertEqual(response.data['processing_status'], 'completed')
        self.assertEqual(response.data['source_name'], 'Test News Source')
    
    # ========================================================================
    # Stats Tests
    # ========================================================================
    
    def test_stats_endpoint(self):
        """Test article stats endpoint."""
        response = self.client.get('/api/articles/stats/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 4)
        self.assertEqual(response.data['quality']['high'], 1)
        self.assertEqual(response.data['quality']['medium'], 1)
        self.assertEqual(response.data['quality']['low'], 1)
        self.assertEqual(response.data['quality']['unscored'], 1)
        self.assertEqual(response.data['ai_detected'], 1)


def run_tests():
    """Run all Article Viewer API tests."""
    import unittest
    from django.test.utils import setup_test_environment
    from django.test.runner import DiscoverRunner
    
    # Setup test environment with isolated test database
    runner = DiscoverRunner(verbosity=2, interactive=False)
    
    # Create test database
    old_config = runner.setup_databases()
    
    try:
        # Run tests
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(ArticleViewerAPITestCase)
        test_runner = unittest.TextTestRunner(verbosity=2)
        result = test_runner.run(suite)
        
        # Print summary
        print("\n" + "=" * 70)
        if result.wasSuccessful():
            print(f"✅ SUCCESS: All {result.testsRun} tests passed!")
        else:
            print(f"❌ FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
            for test, traceback in result.failures + result.errors:
                print(f"\n  {test}:")
                print(f"    {traceback}")
        print("=" * 70)
        
        return result.wasSuccessful()
    finally:
        # Teardown test database
        runner.teardown_databases(old_config)


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
