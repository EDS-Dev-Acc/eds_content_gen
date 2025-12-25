"""
Celery configuration for EMCIP project.

Includes request ID propagation for cross-service tracing.
"""

import os
from celery import Celery
from celery.signals import worker_process_init, task_prerun, task_postrun

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('emcip')

# Load configuration from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Configure task routing (optional, for future scaling)
app.conf.task_routes = {
    'apps.sources.tasks.*': {'queue': 'crawl'},
    'apps.articles.tasks.*': {'queue': 'process'},
    'apps.content.tasks.*': {'queue': 'content'},
}

# Default queue if not specified
app.conf.task_default_queue = 'default'


@task_prerun.connect
def setup_task_request_context(task_id, task, args, kwargs, **signals_kwargs):
    """
    Set up request context at the start of each Celery task.
    
    Extracts request_id from task headers (if passed via celery_request_id_headers)
    and sets up thread-local context for logging correlation.
    """
    try:
        from apps.core.middleware import setup_celery_request_context
        
        # Get headers from task request
        headers = getattr(task.request, 'headers', None) or {}
        setup_celery_request_context(headers)
    except Exception:
        pass  # Don't fail task if context setup fails


@task_postrun.connect
def cleanup_task_request_context(task_id, task, args, kwargs, retval, state, **signals_kwargs):
    """
    Clean up request context after task completes.
    """
    try:
        from apps.core.middleware import clear_request_context
        clear_request_context()
    except Exception:
        pass


@worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    """Initialize OpenTelemetry tracing for Celery workers."""
    try:
        from apps.core.tracing import setup_tracing, instrument_celery, instrument_requests
        from django.conf import settings
        
        if getattr(settings, 'OTEL_ENABLED', False):
            setup_tracing(
                service_name=f"{getattr(settings, 'OTEL_SERVICE_NAME', 'emcip')}-worker",
                otlp_endpoint=getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', None),
            )
            instrument_celery()
            instrument_requests()
    except Exception as e:
        print(f"Failed to initialize Celery tracing: {e}")


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
    return {'status': 'ok', 'worker': self.request.hostname}
