"""
Request ID Middleware for EMCIP.

Generates and propagates unique request IDs for tracing.

Features:
- Generates UUID-based request ID for each request
- Accepts incoming X-Request-ID header
- Adds request ID to response headers
- Injects request ID into thread-local logging context
- Provides context for Celery task correlation

Usage:
    Add to MIDDLEWARE in settings:
    
    MIDDLEWARE = [
        ...
        'apps.core.middleware.RequestIDMiddleware',
        ...
    ]

Access request ID in views:
    from apps.core.middleware import get_request_id
    
    def my_view(request):
        request_id = get_request_id()
        # or
        request_id = request.request_id
"""

import uuid
import threading
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Thread-local storage for request context
_request_context = threading.local()


def get_request_id():
    """
    Get the current request ID from thread-local storage.
    
    Returns None if called outside of a request context.
    """
    return getattr(_request_context, 'request_id', None)


def get_request_context():
    """
    Get the full request context from thread-local storage.
    
    Returns dict with request_id and other context.
    """
    return {
        'request_id': getattr(_request_context, 'request_id', None),
        'user_id': getattr(_request_context, 'user_id', None),
        'path': getattr(_request_context, 'path', None),
    }


def set_request_context(request_id, user_id=None, path=None):
    """
    Set request context in thread-local storage.
    
    Useful for setting context in Celery tasks.
    """
    _request_context.request_id = request_id
    _request_context.user_id = user_id
    _request_context.path = path


def clear_request_context():
    """Clear request context from thread-local storage."""
    _request_context.request_id = None
    _request_context.user_id = None
    _request_context.path = None


class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware to handle request IDs for tracing.
    
    Flow:
    1. Check for incoming X-Request-ID header
    2. Generate new UUID if not present
    3. Store in thread-local for access in views/logging
    4. Attach to request object as request.request_id
    5. Add to response headers
    """
    
    REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
    RESPONSE_HEADER = 'X-Request-ID'
    
    def process_request(self, request):
        """Extract or generate request ID."""
        # Check for incoming request ID
        request_id = request.META.get(self.REQUEST_ID_HEADER)
        
        # Validate or generate new ID
        if request_id:
            # Validate it's a valid UUID format
            try:
                uuid.UUID(request_id)
            except (ValueError, TypeError):
                # Invalid format, generate new
                request_id = str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())
        
        # Store in thread-local
        _request_context.request_id = request_id
        _request_context.path = request.path
        
        # Store user ID if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            _request_context.user_id = str(request.user.id)
        else:
            _request_context.user_id = None
        
        # Attach to request object
        request.request_id = request_id
        
        return None
    
    def process_response(self, request, response):
        """Add request ID to response headers."""
        request_id = getattr(request, 'request_id', None)
        
        if request_id:
            response[self.RESPONSE_HEADER] = request_id
        
        # Clear thread-local context
        clear_request_context()
        
        return response
    
    def process_exception(self, request, exception):
        """Ensure context is cleared even on exception."""
        # Context will be cleared in process_response
        return None


class RequestIDFilter(logging.Filter):
    """
    Logging filter that adds request_id to log records.
    
    Usage in LOGGING config:
    
    LOGGING = {
        'filters': {
            'request_id': {
                '()': 'apps.core.middleware.RequestIDFilter',
            },
        },
        'formatters': {
            'verbose': {
                'format': '[{request_id}] {levelname} {name} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
                'filters': ['request_id'],
            },
        },
    }
    """
    
    def filter(self, record):
        """Add request_id to log record."""
        record.request_id = get_request_id() or '-'
        return True


def celery_request_id_headers():
    """
    Get headers to pass to Celery tasks for correlation.
    
    Usage:
        task.apply_async(
            args=[...],
            headers=celery_request_id_headers(),
        )
    """
    request_id = get_request_id()
    if request_id:
        return {'request_id': request_id}
    return {}


def setup_celery_request_context(headers):
    """
    Set up request context in Celery task from headers.
    
    Usage in Celery task:
        @app.task(bind=True)
        def my_task(self, *args):
            setup_celery_request_context(self.request.headers or {})
            # ... task code ...
    """
    request_id = headers.get('request_id')
    if request_id:
        set_request_context(request_id)
    else:
        set_request_context(str(uuid.uuid4()))
