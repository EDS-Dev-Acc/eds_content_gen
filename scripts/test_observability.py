#!/usr/bin/env python
"""
Test script for Phase 8: Observability.

Tests:
1. Structured logging
2. Metrics collection
3. Health checks
4. Performance decorators
5. Request tracing
"""

import os
import sys
import time
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.core.observability import (
    LogContext,
    StructuredLogger,
    get_logger,
    MetricsCollector,
    metrics,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    health_checker,
    register_default_checks,
    timed,
    counted,
    logged,
    tracer,
    record_crawl_metrics,
    record_processing_metrics,
    record_llm_metrics,
)


def test_log_context():
    """Test LogContext creation and conversion."""
    print("\n=== Test 1: LogContext ===")
    
    ctx = LogContext(
        component="crawler",
        operation="fetch_page",
        correlation_id="abc-123",
        source_id="source-456",
    )
    
    data = ctx.to_dict()
    assert data["component"] == "crawler"
    assert data["operation"] == "fetch_page"
    assert data["correlation_id"] == "abc-123"
    print(f"  Context dict: {data}")
    
    # Context without optional fields
    minimal_ctx = LogContext(component="test", operation="run")
    minimal_data = minimal_ctx.to_dict()
    assert "correlation_id" not in minimal_data
    print(f"  Minimal context: {minimal_data}")
    
    print("  PASSED")
    return True


def test_structured_logger():
    """Test StructuredLogger functionality."""
    print("\n=== Test 2: StructuredLogger ===")
    
    logger = StructuredLogger("test_module")
    
    # Test basic logging (won't error)
    logger.info("Test info message")
    logger.debug("Test debug message")
    logger.warning("Test warning message")
    print("  Basic logging works")
    
    # Test with context
    ctx = LogContext(component="test", operation="testing")
    logger.info("Message with context", ctx, extra_field="value")
    print("  Context logging works")
    
    # Test context manager
    with logger.context(LogContext(component="nested", operation="op")):
        logger.info("Inside context")
    print("  Context manager works")
    
    print("  PASSED")
    return True


def test_get_logger():
    """Test get_logger convenience function."""
    print("\n=== Test 3: get_logger ===")
    
    logger = get_logger("mymodule", component="mycomponent")
    assert isinstance(logger, StructuredLogger)
    print(f"  Created logger: {logger._logger.name}")
    
    # Test default context is set
    assert logger._default_context is not None
    assert logger._default_context.component == "mycomponent"
    print(f"  Default context: {logger._default_context.component}")
    
    print("  PASSED")
    return True


def test_metrics_counter():
    """Test metrics counter operations."""
    print("\n=== Test 4: Metrics Counter ===")
    
    # Create fresh metrics for testing
    test_metrics = MetricsCollector.__new__(MetricsCollector)
    test_metrics._metrics = {}
    test_metrics._counters = {}
    test_metrics._gauges = {}
    test_metrics._histograms = {}
    test_metrics._retention_hours = 24
    
    # Increment counter
    test_metrics.increment("test.requests")
    assert test_metrics.get_counter("test.requests") == 1
    print(f"  Counter after 1 increment: {test_metrics.get_counter('test.requests')}")
    
    test_metrics.increment("test.requests", 5)
    assert test_metrics.get_counter("test.requests") == 6
    print(f"  Counter after +5: {test_metrics.get_counter('test.requests')}")
    
    # Counter with tags
    test_metrics.increment("test.tagged", tags={"env": "test"})
    assert test_metrics.get_counter("test.tagged", tags={"env": "test"}) == 1
    print(f"  Tagged counter: {test_metrics.get_counter('test.tagged', tags={'env': 'test'})}")
    
    print("  PASSED")
    return True


def test_metrics_gauge():
    """Test metrics gauge operations."""
    print("\n=== Test 5: Metrics Gauge ===")
    
    test_metrics = MetricsCollector.__new__(MetricsCollector)
    test_metrics._metrics = {}
    test_metrics._counters = {}
    test_metrics._gauges = {}
    test_metrics._histograms = {}
    test_metrics._retention_hours = 24
    
    # Set gauge
    test_metrics.gauge("test.temperature", 72.5)
    assert test_metrics.get_gauge("test.temperature") == 72.5
    print(f"  Gauge value: {test_metrics.get_gauge('test.temperature')}")
    
    # Update gauge
    test_metrics.gauge("test.temperature", 75.0)
    assert test_metrics.get_gauge("test.temperature") == 75.0
    print(f"  Updated gauge: {test_metrics.get_gauge('test.temperature')}")
    
    print("  PASSED")
    return True


def test_metrics_histogram():
    """Test metrics histogram operations."""
    print("\n=== Test 6: Metrics Histogram ===")
    
    test_metrics = MetricsCollector.__new__(MetricsCollector)
    test_metrics._metrics = {}
    test_metrics._counters = {}
    test_metrics._gauges = {}
    test_metrics._histograms = {}
    test_metrics._retention_hours = 24
    
    # Record histogram values
    for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        test_metrics.histogram("test.latency", v)
    
    stats = test_metrics.get_histogram_stats("test.latency")
    assert stats["count"] == 10
    assert stats["min"] == 10
    assert stats["max"] == 100
    assert stats["avg"] == 55
    print(f"  Histogram stats: count={stats['count']}, avg={stats['avg']}, p50={stats['p50']}")
    
    print("  PASSED")
    return True


def test_metrics_timer():
    """Test metrics timer context manager."""
    print("\n=== Test 7: Metrics Timer ===")
    
    test_metrics = MetricsCollector.__new__(MetricsCollector)
    test_metrics._metrics = {}
    test_metrics._counters = {}
    test_metrics._gauges = {}
    test_metrics._histograms = {}
    test_metrics._retention_hours = 24
    
    # Time an operation
    with test_metrics.timer("test.operation"):
        time.sleep(0.01)  # 10ms
    
    # Check duration was recorded
    stats = test_metrics.get_histogram_stats("test.operation_duration_ms")
    assert stats["count"] == 1
    assert stats["min"] >= 10  # At least 10ms
    print(f"  Timer recorded: {stats['min']:.1f}ms")
    
    # Check count was incremented
    assert test_metrics.get_counter("test.operation_count") == 1
    print(f"  Call count: {test_metrics.get_counter('test.operation_count')}")
    
    print("  PASSED")
    return True


def test_health_check_result():
    """Test HealthCheckResult creation."""
    print("\n=== Test 8: HealthCheckResult ===")
    
    result = HealthCheckResult(
        name="test_check",
        status=HealthStatus.HEALTHY,
        message="All good",
        details={"version": "1.0"},
    )
    
    assert result.name == "test_check"
    assert result.status == HealthStatus.HEALTHY
    print(f"  Result: {result.name} = {result.status.value}")
    
    # Test status values
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"
    print(f"  Status values verified")
    
    print("  PASSED")
    return True


def test_health_checker():
    """Test HealthChecker registry and execution."""
    print("\n=== Test 9: HealthChecker ===")
    
    # Create fresh checker for testing
    test_checker = HealthChecker.__new__(HealthChecker)
    test_checker._checks = {}
    
    # Register a simple check
    def simple_check():
        return HealthCheckResult(
            name="simple",
            status=HealthStatus.HEALTHY,
            message="OK",
        )
    
    test_checker.register("simple", simple_check)
    
    # Run the check
    result = test_checker.check("simple")
    assert result.status == HealthStatus.HEALTHY
    assert result.duration_ms > 0
    print(f"  Check result: {result.status.value} ({result.duration_ms:.2f}ms)")
    
    # Register a failing check
    def failing_check():
        return HealthCheckResult(
            name="failing",
            status=HealthStatus.UNHEALTHY,
            message="Connection failed",
        )
    
    test_checker.register("failing", failing_check)
    
    # Run all checks
    all_results = test_checker.check_all()
    assert all_results["status"] == "unhealthy"  # One check failed
    print(f"  All checks status: {all_results['status']}")
    print(f"  Individual: {list(all_results['checks'].keys())}")
    
    print("  PASSED")
    return True


def test_default_health_checks():
    """Test that default health checks are registered."""
    print("\n=== Test 10: Default Health Checks ===")
    
    # Ensure defaults are registered
    register_default_checks()
    
    checks = health_checker.list_checks()
    assert "database" in checks
    assert "redis" in checks
    assert "disk_space" in checks
    print(f"  Registered checks: {checks}")
    
    # Run database check
    db_result = health_checker.check("database")
    print(f"  Database check: {db_result.status.value} - {db_result.message}")
    
    # Run disk check
    disk_result = health_checker.check("disk_space")
    print(f"  Disk check: {disk_result.status.value} - {disk_result.message}")
    
    print("  PASSED")
    return True


def test_timed_decorator():
    """Test @timed decorator."""
    print("\n=== Test 11: @timed Decorator ===")
    
    # Clear metrics
    metrics.clear()
    
    @timed("test.decorated_function")
    def slow_function():
        time.sleep(0.01)
        return "done"
    
    result = slow_function()
    assert result == "done"
    
    # Check metrics were recorded
    stats = metrics.get_histogram_stats("test.decorated_function_duration_ms")
    assert stats["count"] == 1
    assert stats["min"] >= 10
    print(f"  Decorated function duration: {stats['min']:.1f}ms")
    
    print("  PASSED")
    return True


def test_counted_decorator():
    """Test @counted decorator."""
    print("\n=== Test 12: @counted Decorator ===")
    
    # Clear metrics
    metrics.clear()
    
    @counted("test.call_counter")
    def simple_function():
        return 42
    
    # Call multiple times
    for _ in range(5):
        simple_function()
    
    count = metrics.get_counter("test.call_counter")
    assert count == 5
    print(f"  Call count: {count}")
    
    print("  PASSED")
    return True


def test_request_tracer():
    """Test RequestTracer functionality."""
    print("\n=== Test 13: Request Tracer ===")
    
    # New trace
    trace_id = tracer.new_trace()
    assert trace_id is not None
    assert tracer.correlation_id == trace_id
    print(f"  New trace: {trace_id[:8]}...")
    
    # Context manager
    with tracer.trace("custom-id-123") as tid:
        assert tid == "custom-id-123"
        assert tracer.correlation_id == "custom-id-123"
        print(f"  In context: {tracer.correlation_id}")
    
    # Restored after context
    assert tracer.correlation_id == trace_id
    print(f"  Restored: {tracer.correlation_id[:8]}...")
    
    print("  PASSED")
    return True


def test_convenience_metrics():
    """Test convenience metric recording functions."""
    print("\n=== Test 14: Convenience Metrics ===")
    
    # Clear metrics
    metrics.clear()
    
    # Record crawl metrics
    record_crawl_metrics(
        source_id="source-123",
        articles_found=50,
        articles_new=10,
        duration_ms=5000,
        success=True,
    )
    
    assert metrics.get_counter("crawler.runs", {"source_id": "source-123", "success": "true"}) == 1
    print("  Crawl metrics recorded")
    
    # Record processing metrics
    record_processing_metrics(
        article_id="article-456",
        stage="extraction",
        duration_ms=200,
        success=True,
    )
    
    assert metrics.get_counter("processing.extraction", {"stage": "extraction", "success": "true"}) == 1
    print("  Processing metrics recorded")
    
    # Record LLM metrics
    record_llm_metrics(
        model="claude-sonnet-4",
        prompt_name="ai_detection",
        input_tokens=1000,
        output_tokens=200,
        duration_ms=1500,
        cached=False,
    )
    
    assert metrics.get_counter("llm.requests", {"model": "claude-sonnet-4", "prompt": "ai_detection", "cached": "false"}) == 1
    print("  LLM metrics recorded")
    
    print("  PASSED")
    return True


def test_metrics_export():
    """Test metrics export functionality."""
    print("\n=== Test 15: Metrics Export ===")
    
    # Clear and add some metrics
    metrics.clear()
    metrics.increment("export.test", 5)
    metrics.gauge("export.gauge", 42.5)
    metrics.histogram("export.histogram", 100)
    
    # Export all metrics
    exported = metrics.get_all_metrics()
    
    assert "counters" in exported
    assert "gauges" in exported
    assert "histograms" in exported
    assert "timestamp" in exported
    print(f"  Exported keys: {list(exported.keys())}")
    print(f"  Counters: {exported['counters']}")
    print(f"  Gauges: {exported['gauges']}")
    
    print("  PASSED")
    return True


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_log_context,
        test_structured_logger,
        test_get_logger,
        test_metrics_counter,
        test_metrics_gauge,
        test_metrics_histogram,
        test_metrics_timer,
        test_health_check_result,
        test_health_checker,
        test_default_health_checks,
        test_timed_decorator,
        test_counted_decorator,
        test_request_tracer,
        test_convenience_metrics,
        test_metrics_export,
    ]
    
    print("=" * 60)
    print("Phase 8: Observability Tests")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  FAILED: {test.__name__} returned False")
        except Exception as e:
            failed += 1
            print(f"  FAILED: {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\nAll Phase 8 tests passed!")
        return True
    else:
        print(f"\n{failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
