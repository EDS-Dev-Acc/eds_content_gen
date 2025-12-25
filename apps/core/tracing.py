"""
OpenTelemetry Tracing Configuration.

Phase 15: Distributed tracing for observability.

This module provides:
- OTLP exporter configuration
- Django instrumentation
- Celery instrumentation
- Custom span creation utilities
- Request ID correlation
"""

import logging
from functools import wraps
from typing import Optional, Callable, Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Flag to track if tracing is initialized
_tracing_initialized = False

# Try to import OpenTelemetry, gracefully degrade if not installed
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    logger.info("OpenTelemetry not installed - tracing disabled")


def setup_tracing(
    service_name: str = "emcip",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
) -> bool:
    """
    Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service for tracing
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        console_export: Whether to also export spans to console (for debugging)
    
    Returns:
        True if tracing was initialized, False otherwise
    """
    global _tracing_initialized
    
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available - skipping tracing setup")
        return False
    
    if _tracing_initialized:
        logger.debug("Tracing already initialized")
        return True
    
    try:
        # Create resource with service info
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: getattr(settings, 'VERSION', '1.0.0'),
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: 'development' if settings.DEBUG else 'production',
        })
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add OTLP exporter if endpoint provided
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OTLP exporter configured: {otlp_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to configure OTLP exporter: {e}")
        
        # Add console exporter for debugging
        if console_export or settings.DEBUG:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.debug("Console span exporter enabled")
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        _tracing_initialized = True
        logger.info(f"OpenTelemetry tracing initialized for {service_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return False


def instrument_django():
    """Instrument Django with OpenTelemetry."""
    if not OTEL_AVAILABLE:
        return False
    
    try:
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        DjangoInstrumentor().instrument()
        logger.info("Django instrumented with OpenTelemetry")
        return True
    except Exception as e:
        logger.warning(f"Failed to instrument Django: {e}")
        return False


def instrument_celery():
    """Instrument Celery with OpenTelemetry."""
    if not OTEL_AVAILABLE:
        return False
    
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        CeleryInstrumentor().instrument()
        logger.info("Celery instrumented with OpenTelemetry")
        return True
    except Exception as e:
        logger.warning(f"Failed to instrument Celery: {e}")
        return False


def instrument_requests():
    """Instrument requests library with OpenTelemetry."""
    if not OTEL_AVAILABLE:
        return False
    
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
        logger.info("Requests library instrumented with OpenTelemetry")
        return True
    except Exception as e:
        logger.warning(f"Failed to instrument requests: {e}")
        return False


def instrument_redis():
    """Instrument Redis with OpenTelemetry."""
    if not OTEL_AVAILABLE:
        return False
    
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.info("Redis instrumented with OpenTelemetry")
        return True
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")
        return False


def get_tracer(name: str = "emcip"):
    """Get a tracer instance."""
    if not OTEL_AVAILABLE or trace is None:
        return None
    return trace.get_tracer(name)


def create_span(
    name: str,
    attributes: Optional[dict] = None,
    kind: Optional[Any] = None,
):
    """
    Create a new span context manager.
    
    Usage:
        with create_span("my_operation", {"key": "value"}) as span:
            # do work
            span.set_attribute("result", "success")
    """
    tracer = get_tracer()
    if tracer is None:
        # Return a no-op context manager
        from contextlib import nullcontext
        return nullcontext()
    
    if kind is None:
        kind = trace.SpanKind.INTERNAL
    
    return tracer.start_as_current_span(
        name,
        attributes=attributes,
        kind=kind,
    )


def traced(
    name: Optional[str] = None,
    attributes: Optional[dict] = None,
):
    """
    Decorator to trace a function.
    
    Usage:
        @traced("my_operation")
        def my_function():
            pass
        
        @traced(attributes={"component": "crawler"})
        def crawl_page():
            pass
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    if span and hasattr(span, 'set_status'):
                        span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    if span and hasattr(span, 'set_status'):
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def add_request_id_to_span(request_id: str):
    """Add request ID to current span for correlation."""
    if not OTEL_AVAILABLE or trace is None:
        return
    
    span = trace.get_current_span()
    if span:
        span.set_attribute("request.id", request_id)


def get_trace_context() -> dict:
    """
    Get current trace context for propagation.
    
    Returns dict with traceparent and tracestate headers.
    """
    if not OTEL_AVAILABLE:
        return {}
    
    try:
        propagator = TraceContextTextMapPropagator()
        carrier = {}
        propagator.inject(carrier)
        return carrier
    except Exception:
        return {}


# Initialize tracing on module load if configured
def auto_init():
    """Auto-initialize tracing from Django settings."""
    if not OTEL_AVAILABLE:
        return
    
    otlp_endpoint = getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', None)
    if otlp_endpoint or getattr(settings, 'OTEL_ENABLED', False):
        setup_tracing(
            service_name=getattr(settings, 'OTEL_SERVICE_NAME', 'emcip'),
            otlp_endpoint=otlp_endpoint,
            console_export=getattr(settings, 'OTEL_CONSOLE_EXPORT', False),
        )
        
        # Instrument libraries
        instrument_django()
        instrument_requests()
        instrument_redis()
