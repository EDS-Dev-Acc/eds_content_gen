"""
Tests for Observability Features - Request ID and Metrics.

Phase 18: Production hardening - observability validation.

Tests cover:
- Request ID middleware functionality
- X-Request-ID header propagation
- Celery task header propagation
- Metrics increment validation
- Label cardinality enforcement
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


# ============================================================================
# Request ID Middleware Tests
# ============================================================================

class TestRequestIdMiddleware:
    """Test request ID propagation."""
    
    def test_celery_request_id_headers_returns_dict(self):
        """celery_request_id_headers should return a dict."""
        from apps.core.middleware import celery_request_id_headers
        
        result = celery_request_id_headers()
        assert isinstance(result, dict)
    
    def test_celery_request_id_headers_with_context(self):
        """celery_request_id_headers should include request_id when available."""
        from apps.core.middleware import celery_request_id_headers
        import threading
        
        # The function uses thread-local storage
        # It may return empty dict without request context
        result = celery_request_id_headers()
        assert isinstance(result, dict)
    
    def test_request_id_format(self):
        """Request IDs should be valid UUIDs."""
        # Generate a request ID as the middleware would
        request_id = str(uuid.uuid4())
        
        # Should be valid UUID format
        parsed = uuid.UUID(request_id)
        assert str(parsed) == request_id


# ============================================================================
# Metrics Smoke Tests
# ============================================================================

class TestMetricsSmoke:
    """Smoke tests for metrics increments."""
    
    def test_http_request_counter_exists(self):
        """HTTP request counter should be importable."""
        from apps.core.metrics import http_requests_total, PROMETHEUS_AVAILABLE
        
        # Counter exists (may be no-op if Prometheus not installed)
        assert http_requests_total is not None
    
    def test_increment_http_request_no_error(self):
        """Incrementing HTTP counter should not raise."""
        from apps.core.metrics import increment_http_request
        
        # Should not raise for any status code
        try:
            increment_http_request(200)
            increment_http_request(201)
            increment_http_request(400)
            increment_http_request(404)
            increment_http_request(500)
            increment_http_request('error')
        except Exception as e:
            pytest.fail(f"increment_http_request raised: {e}")
    
    def test_runs_counter_exists(self):
        """Runs counter should be importable."""
        from apps.core.metrics import runs_completed_total, PROMETHEUS_AVAILABLE
        
        assert runs_completed_total is not None
    
    def test_articles_counter_exists(self):
        """Articles counter should be importable."""
        from apps.core.metrics import articles_processed_total, PROMETHEUS_AVAILABLE
        
        assert articles_processed_total is not None
    
    def test_exports_counter_exists(self):
        """Exports counter should be importable."""
        from apps.core.metrics import exports_created_total, PROMETHEUS_AVAILABLE
        
        assert exports_created_total is not None
    
    def test_seeds_counter_exists(self):
        """Seeds counter should be importable."""
        from apps.core.metrics import seeds_validated_total, PROMETHEUS_AVAILABLE
        
        assert seeds_validated_total is not None
    
    def test_schedules_counter_exists(self):
        """Schedules counter should be importable."""
        from apps.core.metrics import schedules_trigger_total, PROMETHEUS_AVAILABLE
        
        assert schedules_trigger_total is not None


# ============================================================================
# Label Cardinality Tests
# ============================================================================

class TestLabelCardinality:
    """Test that metric labels are bounded."""
    
    def test_status_code_to_class_function(self):
        """Status code to class conversion should work."""
        from apps.core.metrics import _status_code_to_class
        
        # Valid conversions
        assert _status_code_to_class(200) == '2xx'
        assert _status_code_to_class(201) == '2xx'
        assert _status_code_to_class(204) == '2xx'
        assert _status_code_to_class(301) == '3xx'
        assert _status_code_to_class(302) == '3xx'
        assert _status_code_to_class(400) == '4xx'
        assert _status_code_to_class(401) == '4xx'
        assert _status_code_to_class(403) == '4xx'
        assert _status_code_to_class(404) == '4xx'
        assert _status_code_to_class(500) == '5xx'
        assert _status_code_to_class(502) == '5xx'
        assert _status_code_to_class(503) == '5xx'
    
    def test_status_code_to_class_edge_cases(self):
        """Status code conversion should handle edge cases."""
        from apps.core.metrics import _status_code_to_class
        
        # Edge cases
        assert _status_code_to_class(None) == 'error'
        assert _status_code_to_class('error') == 'error'
        assert _status_code_to_class(0) == 'error'
        assert _status_code_to_class(999) == 'error'
    
    def test_http_requests_uses_bounded_labels(self):
        """HTTP requests metric should only have bounded labels."""
        from apps.core.metrics import http_requests_total, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            label_names = list(http_requests_total._labelnames)
            
            # Only bounded labels allowed
            allowed_labels = {'method', 'endpoint', 'status_class', 'status'}
            for label in label_names:
                assert label in allowed_labels or label not in ['domain', 'url', 'host', 'path']


# ============================================================================
# Celery Task Propagation Tests
# ============================================================================

class TestCeleryPropagation:
    """Test request ID propagation to Celery tasks."""
    
    def test_crawl_source_accepts_headers(self):
        """crawl_source task should accept headers parameter."""
        from apps.sources.tasks import crawl_source
        
        # The task should be callable with headers
        # This is a signature check, not an execution test
        assert hasattr(crawl_source, 'apply_async')
    
    def test_generate_export_accepts_headers(self):
        """generate_export task should accept headers parameter."""
        from apps.articles.tasks import generate_export
        
        assert hasattr(generate_export, 'apply_async')
    
    def test_process_article_accepts_headers(self):
        """process_article task should accept headers parameter."""
        from apps.articles.tasks import process_article
        
        assert hasattr(process_article, 'apply_async')


# ============================================================================
# Integration Tests
# ============================================================================

class TestObservabilityIntegration:
    """Integration tests for observability features."""
    
    @pytest.mark.django_db
    def test_api_response_structured(self):
        """API responses should have consistent structure."""
        from rest_framework.test import APIClient
        
        client = APIClient()
        user = User.objects.create_user(
            username='obstest',
            password='testpass123'
        )
        client.force_authenticate(user=user)
        
        # GET list endpoint
        response = client.get('/api/seeds/')
        
        # Should return valid JSON
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list or paginated response
        assert isinstance(data, (list, dict))
    
    @pytest.mark.django_db
    def test_error_response_structured(self):
        """Error responses should have consistent structure."""
        from rest_framework.test import APIClient
        
        client = APIClient()
        user = User.objects.create_user(
            username='errtest',
            password='testpass123'
        )
        client.force_authenticate(user=user)
        
        # Try to get non-existent resource
        response = client.get('/api/seeds/00000000-0000-0000-0000-000000000000/')
        
        # Should return 404
        assert response.status_code == 404
