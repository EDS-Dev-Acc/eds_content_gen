"""
Prometheus Metrics for EMCIP.

Provides application-level metrics for monitoring.

Metrics included:
- seeds_import_total: Counter for seed imports
- seeds_validate_duration_seconds: Histogram for validation time
- seeds_discover_entrypoints_total: Counter for discovery operations
- runs_started_total: Counter for crawl runs
- runs_completed_total: Counter with status labels
- schedules_trigger_total: Counter for schedule triggers
- llm_token_usage_total: Counter for LLM token consumption
- articles_processed_total: Counter for article processing
- http_requests_total: Counter for HTTP requests

Cardinality Guidelines:
- All labels MUST be low-cardinality (small, bounded set of values)
- ALLOWED label values: status enums, format enums, trigger types
- FORBIDDEN label values: URLs, IDs, hostnames, user-generated strings
- If per-resource metrics needed, use structured logging instead

Usage:
    from apps.core.metrics import (
        seeds_import_counter,
        increment_seeds_import,
        observe_validation_duration,
    )
    
    # In view
    increment_seeds_import(count=10, status='success')
    
    # With context manager for timing
    with observe_validation_duration():
        # ... validation code ...

Setup:
    Add to urls.py:
        from apps.core.metrics import metrics_view
        urlpatterns = [
            path('metrics/', metrics_view, name='prometheus-metrics'),
        ]
"""

import time
from functools import wraps
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Try to import prometheus_client, provide stubs if not available
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed - metrics will be no-ops")


# ============================================================================
# Metric Definitions
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # Seeds metrics
    seeds_import_total = Counter(
        'emcip_seeds_import_total',
        'Total seeds import operations',
        ['status', 'format']  # status: success/error, format: urls/csv/opml
    )
    
    seeds_validate_duration_seconds = Histogram(
        'emcip_seeds_validate_duration_seconds',
        'Time spent validating seeds',
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    )
    
    seeds_discover_total = Counter(
        'emcip_seeds_discover_entrypoints_total',
        'Total entrypoint discovery operations',
        ['status']  # status: success/error
    )
    
    seeds_test_crawl_total = Counter(
        'emcip_seeds_test_crawl_total',
        'Total test crawl operations',
        ['status']
    )
    
    # Runs/Crawl metrics
    runs_started_total = Counter(
        'emcip_runs_started_total',
        'Total crawl runs started',
        ['trigger']  # trigger: api/schedule/manual
    )
    
    runs_completed_total = Counter(
        'emcip_runs_completed_total',
        'Total crawl runs completed',
        ['status']  # status: completed/failed/cancelled
    )
    
    runs_duration_seconds = Histogram(
        'emcip_runs_duration_seconds',
        'Duration of crawl runs',
        buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
    )
    
    runs_articles_found = Histogram(
        'emcip_runs_articles_found',
        'Articles found per run',
        buckets=[0, 1, 5, 10, 25, 50, 100, 250, 500, 1000]
    )
    
    # Schedule metrics
    # Note: schedule_name kept but should be bounded (schedules are operator-created
    # and typically limited). If cardinality becomes an issue, remove this label.
    schedules_trigger_total = Counter(
        'emcip_schedules_trigger_total',
        'Total schedule triggers',
        ['status']  # status: success/error - removed schedule_name to reduce cardinality
    )
    
    schedules_active = Gauge(
        'emcip_schedules_active',
        'Number of active (enabled) schedules'
    )
    
    # Articles metrics
    articles_processed_total = Counter(
        'emcip_articles_processed_total',
        'Total articles processed',
        ['status']  # status: success/error
    )
    
    articles_score_distribution = Histogram(
        'emcip_articles_score',
        'Distribution of article scores',
        buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    )
    
    # LLM metrics
    llm_requests_total = Counter(
        'emcip_llm_requests_total',
        'Total LLM API requests',
        ['provider', 'model', 'status']  # status: success/error
    )
    
    llm_token_usage_total = Counter(
        'emcip_llm_token_usage_total',
        'Total LLM tokens used',
        ['provider', 'model', 'type']  # type: input/output
    )
    
    llm_request_duration_seconds = Histogram(
        'emcip_llm_request_duration_seconds',
        'LLM request duration',
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
    )
    
    # HTTP metrics
    # Note: Removed 'domain' label to prevent cardinality explosion.
    # If domain-level metrics are needed, use sampling or aggregate by TLD.
    http_requests_total = Counter(
        'emcip_http_requests_total',
        'Total HTTP requests to external sites',
        ['status_class']  # status_class: 2xx, 3xx, 4xx, 5xx, error
    )
    
    http_request_duration_seconds = Histogram(
        'emcip_http_request_duration_seconds',
        'External HTTP request duration',
        buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    )
    
    # Content generation metrics
    content_opportunities_found = Counter(
        'emcip_content_opportunities_found_total',
        'Total content opportunities identified',
        ['opportunity_type']
    )
    
    content_drafts_generated = Counter(
        'emcip_content_drafts_generated_total',
        'Total content drafts generated',
        ['status']
    )
    
    # Export metrics
    exports_created_total = Counter(
        'emcip_exports_created_total',
        'Total export jobs created',
        ['format', 'status']  # format: csv/json/markdown_zip, status: success/error
    )
    
    exports_rows_total = Counter(
        'emcip_exports_rows_total',
        'Total rows exported',
        ['format']
    )


# ============================================================================
# Helper Functions
# ============================================================================

def increment_seeds_import(count=1, status='success', format='urls'):
    """Increment seeds import counter."""
    if PROMETHEUS_AVAILABLE:
        seeds_import_total.labels(status=status, format=format).inc(count)


def increment_seeds_discover(status='success'):
    """Increment seeds discover counter."""
    if PROMETHEUS_AVAILABLE:
        seeds_discover_total.labels(status=status).inc()


def increment_test_crawl(status='success'):
    """Increment test crawl counter."""
    if PROMETHEUS_AVAILABLE:
        seeds_test_crawl_total.labels(status=status).inc()


def increment_runs_started(trigger='api'):
    """Increment runs started counter."""
    if PROMETHEUS_AVAILABLE:
        runs_started_total.labels(trigger=trigger).inc()


def increment_runs_completed(status='completed'):
    """Increment runs completed counter."""
    if PROMETHEUS_AVAILABLE:
        runs_completed_total.labels(status=status).inc()


def increment_schedules_trigger(status='success'):
    """
    Increment schedule trigger counter.
    
    Note: schedule_name label removed to prevent cardinality issues.
    Use logging/tracing for per-schedule debugging.
    """
    if PROMETHEUS_AVAILABLE:
        schedules_trigger_total.labels(status=status).inc()


def observe_run_duration(duration_seconds):
    """Record run duration."""
    if PROMETHEUS_AVAILABLE:
        runs_duration_seconds.observe(duration_seconds)


def observe_articles_found(count):
    """Record articles found per run."""
    if PROMETHEUS_AVAILABLE:
        runs_articles_found.observe(count)


def increment_articles_processed(status='success'):
    """Increment articles processed counter."""
    if PROMETHEUS_AVAILABLE:
        articles_processed_total.labels(status=status).inc()


def observe_article_score(score):
    """Record article score."""
    if PROMETHEUS_AVAILABLE:
        articles_score_distribution.observe(score)


def increment_llm_request(provider='openai', model='gpt-4', status='success'):
    """Increment LLM request counter."""
    if PROMETHEUS_AVAILABLE:
        llm_requests_total.labels(provider=provider, model=model, status=status).inc()


def increment_llm_tokens(count, provider='openai', model='gpt-4', token_type='output'):
    """Increment LLM token usage."""
    if PROMETHEUS_AVAILABLE:
        llm_token_usage_total.labels(provider=provider, model=model, type=token_type).inc(count)


def observe_llm_duration(duration_seconds, provider='openai', model='gpt-4'):
    """Record LLM request duration."""
    if PROMETHEUS_AVAILABLE:
        llm_request_duration_seconds.observe(duration_seconds)


def _status_code_to_class(status_code) -> str:
    """Convert status code to class label (2xx, 3xx, etc.)."""
    try:
        code = int(status_code)
        if 200 <= code < 300:
            return '2xx'
        elif 300 <= code < 400:
            return '3xx'
        elif 400 <= code < 500:
            return '4xx'
        elif 500 <= code < 600:
            return '5xx'
        else:
            return 'other'
    except (ValueError, TypeError):
        return 'error'


def increment_http_request(status_code):
    """
    Increment HTTP request counter.
    
    Note: Domain labels removed to prevent cardinality explosion.
    Status codes are grouped into classes (2xx, 3xx, 4xx, 5xx).
    """
    if PROMETHEUS_AVAILABLE:
        status_class = _status_code_to_class(status_code)
        http_requests_total.labels(status_class=status_class).inc()


def observe_http_duration(duration_seconds):
    """Record HTTP request duration."""
    if PROMETHEUS_AVAILABLE:
        http_request_duration_seconds.observe(duration_seconds)


def increment_opportunities_found(opportunity_type='gap'):
    """Increment content opportunities counter."""
    if PROMETHEUS_AVAILABLE:
        content_opportunities_found.labels(opportunity_type=opportunity_type).inc()


def increment_drafts_generated(status='success'):
    """Increment drafts generated counter."""
    if PROMETHEUS_AVAILABLE:
        content_drafts_generated.labels(status=status).inc()


def increment_exports_created(format='csv', status='success'):
    """Increment exports created counter."""
    if PROMETHEUS_AVAILABLE:
        exports_created_total.labels(format=format, status=status).inc()


def increment_exports_rows(count, format='csv'):
    """Increment exports rows counter."""
    if PROMETHEUS_AVAILABLE:
        exports_rows_total.labels(format=format).inc(count)


def update_active_schedules(count):
    """Update active schedules gauge."""
    if PROMETHEUS_AVAILABLE:
        schedules_active.set(count)


# ============================================================================
# Context Managers and Decorators
# ============================================================================

@contextmanager
def observe_validation_duration():
    """Context manager to time seed validation."""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if PROMETHEUS_AVAILABLE:
            seeds_validate_duration_seconds.observe(duration)


@contextmanager
def observe_llm_request_duration(provider='openai', model='gpt-4'):
    """Context manager to time LLM requests."""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if PROMETHEUS_AVAILABLE:
            llm_request_duration_seconds.observe(duration)


def track_http_request(func):
    """
    Decorator to track HTTP request metrics.
    
    Phase 18: Fixed to use status_class label to prevent cardinality explosion.
    Domain label was removed - use logging/tracing for per-domain analysis.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            if PROMETHEUS_AVAILABLE:
                http_request_duration_seconds.observe(duration)
                # Use status_class to avoid cardinality issues
                if hasattr(result, 'status_code'):
                    status_class = _status_code_to_class(result.status_code)
                    http_requests_total.labels(status_class=status_class).inc()
            
            return result
        except Exception as e:
            if PROMETHEUS_AVAILABLE:
                http_requests_total.labels(status_class='error').inc()
            raise
    return wrapper


# ============================================================================
# Metrics View
# ============================================================================

def metrics_view(request):
    """
    Django view to expose Prometheus metrics.
    
    Returns metrics in Prometheus text format.
    """
    from django.http import HttpResponse
    
    if not PROMETHEUS_AVAILABLE:
        return HttpResponse(
            "# prometheus_client not installed\n",
            content_type='text/plain'
        )
    
    # Update gauge metrics before generating output
    try:
        from django_celery_beat.models import PeriodicTask
        active_count = PeriodicTask.objects.filter(enabled=True).count()
        schedules_active.set(active_count)
    except Exception:
        pass
    
    metrics_output = generate_latest()
    return HttpResponse(metrics_output, content_type=CONTENT_TYPE_LATEST)
