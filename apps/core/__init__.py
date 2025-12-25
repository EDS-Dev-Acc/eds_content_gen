"""
Core app for EMCIP.

Provides shared utilities, observability, and health checks.
"""

default_app_config = 'apps.core.apps.CoreConfig'

# Key exports for external use
from .observability import (
    # Logging
    StructuredLogger,
    LogContext,
    get_logger,
    
    # Metrics
    MetricsCollector,
    MetricType,
    Metric,
    
    # Health checks
    HealthChecker,
    HealthStatus,
    HealthCheckResult,
    
    # Decorators
    timed,
    counted,
    logged,
    
    # Tracing
    RequestTracer,
    
    # Convenience functions
    record_crawl_metrics,
    record_processing_metrics,
    record_llm_metrics,
)

__all__ = [
    # Logging
    'StructuredLogger',
    'LogContext',
    'get_logger',
    
    # Metrics
    'MetricsCollector',
    'MetricType',
    'Metric',
    
    # Health checks
    'HealthChecker',
    'HealthStatus',
    'HealthCheckResult',
    
    # Decorators
    'timed',
    'counted',
    'logged',
    
    # Tracing
    'RequestTracer',
    
    # Convenience functions
    'record_crawl_metrics',
    'record_processing_metrics',
    'record_llm_metrics',
]
