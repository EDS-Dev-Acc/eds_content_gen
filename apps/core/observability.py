"""
Observability utilities for EMCIP project.

Phase 8: Structured logging, metrics collection, and monitoring.
"""

import functools
import json
import logging
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Union

from django.conf import settings


# =============================================================================
# Structured Logging
# =============================================================================

class LogLevel(Enum):
    """Log levels with numeric values for comparison."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogContext:
    """
    Structured log context for consistent logging.
    """
    component: str
    operation: str
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    source_id: Optional[str] = None
    article_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "component": self.component,
            "operation": self.operation,
        }
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.user_id:
            result["user_id"] = self.user_id
        if self.source_id:
            result["source_id"] = self.source_id
        if self.article_id:
            result["article_id"] = self.article_id
        if self.extra:
            result.update(self.extra)
        return result


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted logs.
    
    Supports contextual logging with correlation IDs and consistent field names.
    """
    
    def __init__(self, name: str, default_context: Optional[LogContext] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (typically module name).
            default_context: Default context to include in all logs.
        """
        self._logger = logging.getLogger(name)
        self._default_context = default_context
        self._context_stack: List[LogContext] = []

    def _format_message(
        self,
        message: str,
        context: Optional[LogContext] = None,
        **kwargs
    ) -> str:
        """Format message with structured context."""
        log_data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Add default context
        if self._default_context:
            log_data.update(self._default_context.to_dict())
        
        # Add stacked context (most recent wins)
        for ctx in self._context_stack:
            log_data.update(ctx.to_dict())
        
        # Add provided context
        if context:
            log_data.update(context.to_dict())
        
        # Add extra kwargs
        log_data.update(kwargs)
        
        return json.dumps(log_data, default=str)

    @contextmanager
    def context(self, ctx: LogContext):
        """
        Context manager for temporary logging context.
        
        Args:
            ctx: LogContext to use within the block.
        """
        self._context_stack.append(ctx)
        try:
            yield
        finally:
            self._context_stack.pop()

    def debug(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log debug message."""
        self._logger.debug(self._format_message(message, context, level="DEBUG", **kwargs))

    def info(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log info message."""
        self._logger.info(self._format_message(message, context, level="INFO", **kwargs))

    def warning(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log warning message."""
        self._logger.warning(self._format_message(message, context, level="WARNING", **kwargs))

    def error(self, message: str, context: Optional[LogContext] = None, exc_info: bool = False, **kwargs):
        """Log error message."""
        if exc_info:
            kwargs["traceback"] = traceback.format_exc()
        self._logger.error(self._format_message(message, context, level="ERROR", **kwargs))

    def critical(self, message: str, context: Optional[LogContext] = None, exc_info: bool = False, **kwargs):
        """Log critical message."""
        if exc_info:
            kwargs["traceback"] = traceback.format_exc()
        self._logger.critical(self._format_message(message, context, level="CRITICAL", **kwargs))

    def exception(self, message: str, context: Optional[LogContext] = None, **kwargs):
        """Log exception with traceback."""
        self.error(message, context, exc_info=True, **kwargs)


def get_logger(name: str, component: Optional[str] = None) -> StructuredLogger:
    """
    Get a structured logger.
    
    Args:
        name: Logger name.
        component: Default component name for context.
        
    Returns:
        StructuredLogger instance.
    """
    default_ctx = None
    if component:
        default_ctx = LogContext(component=component, operation="")
    return StructuredLogger(name, default_ctx)


# =============================================================================
# Metrics Collection
# =============================================================================

class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """A single metric data point."""
    name: str
    type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


class MetricsCollector:
    """
    Collect and aggregate metrics.
    
    Thread-safe singleton for application-wide metrics.
    """
    
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._metrics: Dict[str, List[Metric]] = {}
                cls._instance._counters: Dict[str, float] = {}
                cls._instance._gauges: Dict[str, float] = {}
                cls._instance._histograms: Dict[str, List[float]] = {}
                cls._instance._retention_hours = 24
        return cls._instance

    def _make_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric with tags."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def increment(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name.
            value: Value to increment by.
            tags: Optional tags for the metric.
        """
        key = self._make_key(name, tags)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value
            self._record(Metric(name, MetricType.COUNTER, self._counters[key], tags=tags or {}))

    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name.
            value: Current value.
            tags: Optional tags for the metric.
        """
        key = self._make_key(name, tags)
        with self._lock:
            self._gauges[key] = value
            self._record(Metric(name, MetricType.GAUGE, value, tags=tags or {}))

    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a histogram value.
        
        Args:
            name: Metric name.
            value: Value to record.
            tags: Optional tags for the metric.
        """
        key = self._make_key(name, tags)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            # Keep only recent values
            self._histograms[key] = self._histograms[key][-1000:]
            self._record(Metric(name, MetricType.HISTOGRAM, value, tags=tags or {}))

    @contextmanager
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Context manager to time an operation.
        
        Args:
            name: Metric name.
            tags: Optional tags for the metric.
            
        Yields:
            None. Duration is recorded on exit.
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.histogram(f"{name}_duration_ms", duration_ms, tags)
            self.increment(f"{name}_count", tags=tags)

    def _record(self, metric: Metric) -> None:
        """Record a metric data point."""
        if metric.name not in self._metrics:
            self._metrics[metric.name] = []
        self._metrics[metric.name].append(metric)

    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        key = self._make_key(name, tags)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value."""
        key = self._make_key(name, tags)
        return self._gauges.get(key)

    def get_histogram_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, tags)
        values = self._histograms.get(key, [])
        
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "min": min(sorted_values),
            "max": max(sorted_values),
            "avg": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.50)],
            "p95": sorted_values[int(count * 0.95)] if count > 1 else sorted_values[0],
            "p99": sorted_values[int(count * 0.99)] if count > 1 else sorted_values[0],
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metric values."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: self.get_histogram_stats(k.split("[")[0])
                    for k in self._histograms.keys()
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

    def clear(self) -> None:
        """Clear all metrics (useful for testing)."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global metrics instance
metrics = MetricsCollector()


# =============================================================================
# Health Checks
# =============================================================================

class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class HealthChecker:
    """
    Health check registry and executor.
    """
    
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        return cls._instance

    def register(self, name: str, check_fn: Callable[[], HealthCheckResult]) -> None:
        """
        Register a health check.
        
        Args:
            name: Unique check name.
            check_fn: Function that returns HealthCheckResult.
        """
        self._checks[name] = check_fn

    def check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Unknown check: {name}",
            )
        
        start = time.perf_counter()
        try:
            result = self._checks[name]()
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        for name in self._checks:
            result = self.check(name)
            results[name] = {
                "status": result.status.value,
                "message": result.message,
                "details": result.details,
                "duration_ms": result.duration_ms,
            }
            
            # Determine overall status
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.DEGRADED
        
        return {
            "status": overall_status.value,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def list_checks(self) -> List[str]:
        """List registered check names."""
        return list(self._checks.keys())


# Global health checker instance
health_checker = HealthChecker()


# =============================================================================
# Built-in Health Checks
# =============================================================================

def check_database() -> HealthCheckResult:
    """Check database connectivity."""
    from django.db import connection
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection successful",
        )
    except Exception as e:
        return HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database error: {e}",
        )


def check_redis() -> HealthCheckResult:
    """Check Redis connectivity."""
    try:
        from django.core.cache import cache
        cache.set("health_check", "ok", 10)
        value = cache.get("health_check")
        
        if value == "ok":
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
            )
        else:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                message="Redis get/set mismatch",
            )
    except Exception as e:
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=f"Redis error: {e}",
        )


def check_celery() -> HealthCheckResult:
    """Check Celery worker availability."""
    try:
        from config.celery import app
        
        # Check if any workers are active
        inspect = app.control.inspect()
        active = inspect.active()
        
        if active:
            worker_count = len(active)
            return HealthCheckResult(
                name="celery",
                status=HealthStatus.HEALTHY,
                message=f"{worker_count} worker(s) active",
                details={"worker_count": worker_count},
            )
        else:
            return HealthCheckResult(
                name="celery",
                status=HealthStatus.DEGRADED,
                message="No active Celery workers",
            )
    except Exception as e:
        return HealthCheckResult(
            name="celery",
            status=HealthStatus.UNHEALTHY,
            message=f"Celery error: {e}",
        )


def check_disk_space() -> HealthCheckResult:
    """Check available disk space."""
    import shutil
    
    try:
        total, used, free = shutil.disk_usage("/")
        free_percent = (free / total) * 100
        
        status = HealthStatus.HEALTHY
        if free_percent < 10:
            status = HealthStatus.UNHEALTHY
        elif free_percent < 20:
            status = HealthStatus.DEGRADED
        
        return HealthCheckResult(
            name="disk_space",
            status=status,
            message=f"{free_percent:.1f}% free",
            details={
                "total_gb": total / (1024**3),
                "used_gb": used / (1024**3),
                "free_gb": free / (1024**3),
                "free_percent": free_percent,
            },
        )
    except Exception as e:
        return HealthCheckResult(
            name="disk_space",
            status=HealthStatus.UNHEALTHY,
            message=f"Disk check error: {e}",
        )


def register_default_checks():
    """Register default health checks."""
    health_checker.register("database", check_database)
    health_checker.register("redis", check_redis)
    health_checker.register("celery", check_celery)
    health_checker.register("disk_space", check_disk_space)


# =============================================================================
# Performance Monitoring Decorators
# =============================================================================

def timed(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """
    Decorator to time function execution.
    
    Args:
        metric_name: Metric name (default: function name).
        tags: Optional metric tags.
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with metrics.timer(name, tags):
                return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.histogram(f"{name}_duration_ms", duration_ms, tags)
                metrics.increment(f"{name}_count", tags=tags)
        
        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


def counted(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """
    Decorator to count function calls.
    
    Args:
        metric_name: Metric name (default: function name).
        tags: Optional metric tags.
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or f"{func.__module__}.{func.__name__}_calls"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics.increment(name, tags=tags)
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def logged(level: str = "INFO", include_args: bool = False, include_result: bool = False):
    """
    Decorator to log function calls.
    
    Args:
        level: Log level.
        include_args: Whether to log function arguments.
        include_result: Whether to log function result.
    """
    def decorator(func: Callable) -> Callable:
        logger = get_logger(func.__module__, component=func.__module__.split(".")[-1])
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            ctx = LogContext(
                component=func.__module__.split(".")[-1],
                operation=func.__name__,
            )
            
            log_kwargs = {}
            if include_args:
                log_kwargs["args"] = str(args)[:200]
                log_kwargs["kwargs"] = str(kwargs)[:200]
            
            logger.info(f"Calling {func.__name__}", ctx, **log_kwargs)
            
            try:
                result = func(*args, **kwargs)
                
                result_kwargs = {}
                if include_result:
                    result_kwargs["result"] = str(result)[:200]
                
                logger.info(f"Completed {func.__name__}", ctx, **result_kwargs)
                return result
            except Exception as e:
                logger.exception(f"Failed {func.__name__}: {e}", ctx)
                raise
        
        return wrapper
    return decorator


def asyncio_iscoroutinefunction(func):
    """Check if function is async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# =============================================================================
# Request Tracing
# =============================================================================

class RequestTracer:
    """
    Request tracing for distributed tracing support.
    """
    
    _local = None

    def __init__(self):
        import threading
        self._local = threading.local()

    @property
    def correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return getattr(self._local, "correlation_id", None)

    @correlation_id.setter
    def correlation_id(self, value: str):
        """Set current correlation ID."""
        self._local.correlation_id = value

    def new_trace(self) -> str:
        """Start a new trace with a new correlation ID."""
        correlation_id = str(uuid.uuid4())
        self._local.correlation_id = correlation_id
        return correlation_id

    @contextmanager
    def trace(self, correlation_id: Optional[str] = None):
        """
        Context manager for request tracing.
        
        Args:
            correlation_id: Optional correlation ID to use.
        """
        old_id = self.correlation_id
        self._local.correlation_id = correlation_id or str(uuid.uuid4())
        try:
            yield self._local.correlation_id
        finally:
            self._local.correlation_id = old_id


# Global tracer instance
tracer = RequestTracer()


# =============================================================================
# Convenience Functions
# =============================================================================

def record_crawl_metrics(
    source_id: str,
    articles_found: int,
    articles_new: int,
    duration_ms: float,
    success: bool = True,
):
    """Record crawler metrics."""
    tags = {"source_id": source_id, "success": str(success).lower()}
    
    metrics.increment("crawler.runs", tags=tags)
    metrics.histogram("crawler.articles_found", articles_found, tags={"source_id": source_id})
    metrics.histogram("crawler.articles_new", articles_new, tags={"source_id": source_id})
    metrics.histogram("crawler.duration_ms", duration_ms, tags={"source_id": source_id})
    
    if not success:
        metrics.increment("crawler.errors", tags={"source_id": source_id})


def record_processing_metrics(
    article_id: str,
    stage: str,
    duration_ms: float,
    success: bool = True,
):
    """Record article processing metrics."""
    tags = {"stage": stage, "success": str(success).lower()}
    
    metrics.increment(f"processing.{stage}", tags=tags)
    metrics.histogram(f"processing.{stage}_duration_ms", duration_ms)
    
    if not success:
        metrics.increment("processing.errors", tags={"stage": stage})


def record_llm_metrics(
    model: str,
    prompt_name: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    cached: bool = False,
):
    """Record LLM usage metrics."""
    tags = {"model": model, "prompt": prompt_name, "cached": str(cached).lower()}
    
    metrics.increment("llm.requests", tags=tags)
    metrics.histogram("llm.input_tokens", input_tokens, tags={"model": model})
    metrics.histogram("llm.output_tokens", output_tokens, tags={"model": model})
    metrics.histogram("llm.duration_ms", duration_ms, tags={"model": model})
