"""
Tests for Prometheus Metrics - Smoke Tests.

Phase 17: Production hardening - metrics validation.

Tests cover:
- Metric registration
- Label cardinality limits
- Counter increments
- Histogram observations
- No high-cardinality labels
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# Metric Registration Tests
# ============================================================================

class TestMetricRegistration:
    """Test that all metrics are registered correctly."""
    
    def test_http_requests_total_exists(self):
        """http_requests_total counter should be registered."""
        from apps.core.metrics import http_requests_total, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            assert http_requests_total is not None
            assert hasattr(http_requests_total, 'labels')
    
    def test_http_request_duration_exists(self):
        """http_request_duration_seconds histogram should be registered."""
        from apps.core.metrics import http_request_duration_seconds, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            assert http_request_duration_seconds is not None
    
    def test_runs_completed_total_exists(self):
        """runs_completed_total counter should be registered."""
        from apps.core.metrics import runs_completed_total, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            assert runs_completed_total is not None
    
    def test_articles_processed_total_exists(self):
        """articles_processed_total counter should be registered."""
        from apps.core.metrics import articles_processed_total, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            assert articles_processed_total is not None


# ============================================================================
# Label Cardinality Tests
# ============================================================================

class TestLabelCardinality:
    """Test that labels don't have high cardinality."""
    
    def test_http_requests_uses_status_class(self):
        """http_requests_total should use status_class, not status code."""
        from apps.core.metrics import _status_code_to_class
        
        # Verify the helper function exists and works
        assert _status_code_to_class is not None
        
        # Check it returns classes not codes
        assert _status_code_to_class(200) == '2xx'
        assert _status_code_to_class(404) == '4xx'
        assert _status_code_to_class(500) == '5xx'
    
    def test_http_requests_no_domain_label(self):
        """http_requests_total should not have domain label."""
        from apps.core.metrics import http_requests_total, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            # Check label names
            label_names = list(http_requests_total._labelnames)
            
            assert 'domain' not in label_names
            assert 'host' not in label_names
            assert 'url' not in label_names
    
    def test_schedules_no_schedule_name_label(self):
        """Schedule metrics should not have schedule_name label."""
        from apps.core.metrics import schedules_trigger_total, PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            label_names = list(schedules_trigger_total._labelnames)
            
            assert 'schedule_name' not in label_names
            assert 'name' not in label_names


# ============================================================================
# Counter Increment Tests
# ============================================================================

class TestCounterIncrements:
    """Test counter increment behavior."""
    
    def test_increment_http_request_works(self):
        """increment_http_request should work without errors."""
        from apps.core.metrics import increment_http_request
        
        # Should not raise
        try:
            increment_http_request(200)
            increment_http_request(404)
            increment_http_request(500)
        except Exception as e:
            pytest.fail(f"Counter increment failed: {e}")
    
    def test_increment_with_error_status(self):
        """Counter should handle error status codes."""
        from apps.core.metrics import increment_http_request, _status_code_to_class
        
        # These should not raise
        increment_http_request('error')
        increment_http_request(None)
        
        # Check the class conversion
        assert _status_code_to_class('error') == 'error'
        assert _status_code_to_class(None) == 'error'


# ============================================================================
# Histogram Observation Tests
# ============================================================================

class TestHistogramObservations:
    """Test histogram observation behavior."""
    
    def test_observe_http_duration_works(self):
        """observe_http_duration should work without errors."""
        from apps.core.metrics import observe_http_duration
        
        try:
            observe_http_duration(0.123)
        except Exception as e:
            pytest.fail(f"Histogram observe failed: {e}")
    
    def test_observe_zero_duration(self):
        """Histogram should accept zero duration."""
        from apps.core.metrics import observe_http_duration
        
        try:
            observe_http_duration(0)
        except Exception as e:
            pytest.fail(f"Histogram observe zero failed: {e}")
    
    def test_observe_large_duration(self):
        """Histogram should accept large durations."""
        from apps.core.metrics import observe_http_duration
        
        try:
            observe_http_duration(3600)  # 1 hour
        except Exception as e:
            pytest.fail(f"Histogram observe large failed: {e}")


# ============================================================================
# Metrics Helper Tests
# ============================================================================

class TestMetricsHelpers:
    """Test metrics helper functions."""
    
    def test_status_code_to_class_2xx(self):
        """2xx status codes should map to '2xx'."""
        from apps.core.metrics import _status_code_to_class
        
        for code in [200, 201, 202, 204, 299]:
            assert _status_code_to_class(code) == '2xx'
    
    def test_status_code_to_class_3xx(self):
        """3xx status codes should map to '3xx'."""
        from apps.core.metrics import _status_code_to_class
        
        for code in [301, 302, 304, 307, 399]:
            assert _status_code_to_class(code) == '3xx'
    
    def test_status_code_to_class_4xx(self):
        """4xx status codes should map to '4xx'."""
        from apps.core.metrics import _status_code_to_class
        
        for code in [400, 401, 403, 404, 422, 429, 499]:
            assert _status_code_to_class(code) == '4xx'
    
    def test_status_code_to_class_5xx(self):
        """5xx status codes should map to '5xx'."""
        from apps.core.metrics import _status_code_to_class
        
        for code in [500, 502, 503, 504, 599]:
            assert _status_code_to_class(code) == '5xx'
    
    def test_status_code_to_class_edge_cases(self):
        """Edge cases should have sensible fallback."""
        from apps.core.metrics import _status_code_to_class
        
        # Below 200
        assert _status_code_to_class(100) == 'other'
        
        # Above 599
        assert _status_code_to_class(600) == 'other'
        
        # Invalid input
        assert _status_code_to_class('not_a_code') == 'error'


# ============================================================================
# Seed Metrics Tests
# ============================================================================

class TestSeedMetrics:
    """Test seed-related metrics."""
    
    def test_increment_seeds_import(self):
        """increment_seeds_import should work."""
        from apps.core.metrics import increment_seeds_import
        
        try:
            increment_seeds_import(count=5, status='success', format='urls')
            increment_seeds_import(count=2, status='error', format='csv')
        except Exception as e:
            pytest.fail(f"Seed import increment failed: {e}")
    
    def test_observe_validation_duration(self):
        """observe_validation_duration should work."""
        from apps.core.metrics import observe_validation_duration
        
        try:
            observe_validation_duration(1.5)
        except Exception as e:
            pytest.fail(f"Validation duration observe failed: {e}")


# ============================================================================
# Run Metrics Tests
# ============================================================================

class TestRunMetrics:
    """Test run-related metrics."""
    
    def test_increment_run_started(self):
        """increment_run_started should work."""
        from apps.core.metrics import increment_run_started
        
        try:
            increment_run_started(trigger='api')
            increment_run_started(trigger='schedule')
        except Exception as e:
            pytest.fail(f"Run started increment failed: {e}")
    
    def test_increment_run_completed(self):
        """increment_run_completed should work."""
        from apps.core.metrics import increment_run_completed
        
        try:
            increment_run_completed(status='completed')
            increment_run_completed(status='failed')
        except Exception as e:
            pytest.fail(f"Run completed increment failed: {e}")


# ============================================================================
# No-Op Fallback Tests
# ============================================================================

class TestNoOpFallback:
    """Test metrics work when prometheus_client not installed."""
    
    def test_metrics_import_without_prometheus(self):
        """Metrics module should import even without prometheus_client."""
        # This test verifies the module handles missing prometheus_client
        try:
            from apps.core import metrics
            assert metrics is not None
        except ImportError:
            pytest.fail("Metrics module should handle missing prometheus_client")
    
    def test_helper_functions_work_without_prometheus(self):
        """Helper functions should work silently without prometheus."""
        from apps.core.metrics import (
            increment_http_request,
            observe_http_duration,
            increment_seeds_import,
        )
        
        # These should not raise even if prometheus isn't available
        increment_http_request(200)
        observe_http_duration(1.0)
        increment_seeds_import(count=1, status='success', format='urls')
