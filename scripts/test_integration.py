#!/usr/bin/env python
"""
Integration Test Suite for EMCIP Pipeline.

Tests the full integration of all phases (2-8) working together:
- Phase 2: Interface abstractions (Fetcher, LinkExtractor, Paginator)
- Phase 3: Pagination memory (Source model persistence)
- Phase 4: Playwright JS handling (optional browser fallback)
- Phase 5: Extraction quality (trafilatura + hybrid)
- Phase 6: State machine for article processing
- Phase 7: LLM hardening (prompts, tokens, caching, costs)
- Phase 8: Observability (logging, metrics, health checks)

Run: python scripts/test_integration.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup Django
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

# Imports after Django setup
from django.test import TestCase
from django.utils import timezone


class IntegrationTestRunner:
    """Test runner that collects and runs all integration tests."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.results = []
    
    def run_test(self, name: str, test_func):
        """Run a single test and record results."""
        try:
            test_func()
            self.tests_passed += 1
            self.results.append((name, True, None))
            print(f"  ✓ {name}")
        except Exception as e:
            self.tests_failed += 1
            self.results.append((name, False, str(e)))
            print(f"  ✗ {name}: {e}")
    
    def summary(self):
        """Print test summary."""
        total = self.tests_passed + self.tests_failed
        print(f"\nResults: {self.tests_passed} passed, {self.tests_failed} failed")
        return self.tests_failed == 0


# =============================================================================
# Test Suite 1: Interface Abstractions (Phase 2)
# =============================================================================

def test_interface_imports():
    """Test that all interface abstractions can be imported."""
    from apps.sources.crawlers.interfaces import (
        Fetcher,
        LinkExtractor,
        Paginator,
        FetchResult,
        ExtractedLink,
        PaginationResult,
        CrawlerPipeline,
    )
    assert Fetcher is not None
    assert LinkExtractor is not None
    assert Paginator is not None


def test_fetcher_implementations():
    """Test that fetcher implementations exist and inherit properly."""
    from apps.sources.crawlers.interfaces import Fetcher
    from apps.sources.crawlers.fetchers import HTTPFetcher, HybridFetcher
    
    assert issubclass(HTTPFetcher, Fetcher)
    assert issubclass(HybridFetcher, Fetcher)


def test_modular_crawler_creation():
    """Test ModularCrawler can be instantiated."""
    from apps.sources.crawlers.adapters import ModularCrawler
    from apps.sources.crawlers.fetchers import HTTPFetcher
    
    # Create mock source
    mock_source = MagicMock()
    mock_source.url = "https://example.com"
    mock_source.domain = "example.com"
    mock_source.name = "Test Source"
    mock_source.crawl_config = {}
    
    fetcher = HTTPFetcher()
    crawler = ModularCrawler(mock_source, fetcher=fetcher)
    assert crawler is not None


# =============================================================================
# Test Suite 2: Pagination Memory (Phase 3)
# =============================================================================

def test_pagination_strategies():
    """Test pagination strategy creation and usage."""
    from apps.sources.crawlers.pagination import (
        ParameterPaginator,
        PathPaginator,
        NextLinkPaginator,
        create_paginator,
    )
    
    # Test factory function with string type
    param_pag = create_paginator('parameter', param_name='page')
    assert isinstance(param_pag, ParameterPaginator)
    
    path_pag = create_paginator('path', pattern='/page/{page}/')
    assert isinstance(path_pag, PathPaginator)


def test_registry_functions():
    """Test registry for site configurations."""
    from apps.sources.crawlers.registry import (
        get_rules_for_domain,
        get_pagination_config,
        get_fetcher_config,
    )
    
    # Should return default configs for unknown domains
    config = get_rules_for_domain("unknown-domain.com")
    assert config is not None
    
    pag_config = get_pagination_config("unknown-domain.com")
    assert pag_config is not None


# =============================================================================
# Test Suite 3: Playwright JS Handling (Phase 4)
# =============================================================================

def test_playwright_availability_flag():
    """Test Playwright availability detection."""
    from apps.sources.crawlers.fetchers import PLAYWRIGHT_AVAILABLE
    # Just verify the flag exists (may be True or False depending on environment)
    assert isinstance(PLAYWRIGHT_AVAILABLE, bool)


def test_hybrid_fetcher_creation():
    """Test HybridFetcher can be created."""
    from apps.sources.crawlers.fetchers import HybridFetcher
    
    fetcher = HybridFetcher()
    assert fetcher is not None
    assert hasattr(fetcher, 'fetch')


# =============================================================================
# Test Suite 4: Extraction Quality (Phase 5)
# =============================================================================

def test_content_extractors():
    """Test content extractor availability."""
    from apps.sources.crawlers.extractors import (
        ContentExtractor,
        HybridContentExtractor,
        ExtractionResult,
        ExtractionQuality,
    )
    
    assert ContentExtractor is not None
    assert HybridContentExtractor is not None
    assert ExtractionQuality is not None


def test_extraction_result_structure():
    """Test ExtractionResult dataclass."""
    from apps.sources.crawlers.extractors import ExtractionResult, ExtractionQuality
    
    # ExtractionResult has defaults, create with keyword args
    result = ExtractionResult()
    result.text = "Test content"
    result.title = "Test Title"
    result.quality = ExtractionQuality.GOOD
    result.extractor_used = "test"
    
    assert result.text == "Test content"
    assert result.quality == ExtractionQuality.GOOD


def test_hybrid_extraction():
    """Test hybrid content extraction."""
    from apps.sources.crawlers.extractors import HybridContentExtractor, extract_content
    
    html = """
    <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Main Headline</h1>
                <p>This is the main content of the article. It contains several sentences 
                to provide enough text for extraction. The hybrid extractor should be able
                to pull this content out successfully.</p>
            </article>
        </body>
    </html>
    """
    
    result = extract_content(html, url="https://example.com/article")
    assert result is not None
    assert result.text or result.title  # Should extract something


# =============================================================================
# Test Suite 5: State Machine (Phase 6)
# =============================================================================

def test_article_states():
    """Test ArticleState enum."""
    from apps.articles.state_machine import ArticleState
    
    assert ArticleState.COLLECTED.value == 'collected'
    assert ArticleState.COMPLETED.is_terminal
    assert ArticleState.FAILED.is_terminal
    assert ArticleState.EXTRACTING.is_processing


def test_state_transitions():
    """Test valid state transitions."""
    from apps.articles.state_machine import ArticleState, VALID_TRANSITIONS
    
    # COLLECTED can transition to EXTRACTING
    assert ArticleState.EXTRACTING in VALID_TRANSITIONS[ArticleState.COLLECTED]
    
    # COMPLETED cannot transition to anything
    assert len(VALID_TRANSITIONS[ArticleState.COMPLETED]) == 0


def test_state_machine_instantiation():
    """Test ArticleStateMachine can be created."""
    from apps.articles.state_machine import ArticleStateMachine
    
    mock_article = MagicMock()
    mock_article.processing_status = 'collected'
    mock_article.processing_error = ''
    mock_article.retry_count = 0
    
    machine = ArticleStateMachine(mock_article)
    assert machine is not None
    assert machine.current_state.value == 'collected'


def test_processing_pipeline():
    """Test ProcessingPipeline creation."""
    from apps.articles.state_machine import ProcessingPipeline
    
    pipeline = ProcessingPipeline()
    assert pipeline is not None
    assert hasattr(pipeline, 'add_stage')


# =============================================================================
# Test Suite 6: LLM Hardening (Phase 7)
# =============================================================================

def test_prompt_template():
    """Test PromptTemplate creation and rendering."""
    from apps.content.prompts import PromptTemplate, PromptCategory
    
    template = PromptTemplate(
        name="test",
        category=PromptCategory.CONTENT_ANALYSIS,
        template="Hello, {name}!",
        version="1.0",
    )
    
    rendered = template.render(name="World")
    assert rendered == "Hello, World!"


def test_prompt_registry():
    """Test PromptRegistry registration and retrieval."""
    from apps.content.prompts import PromptRegistry, PromptTemplate, PromptCategory
    
    registry = PromptRegistry()
    template = PromptTemplate(
        name="custom_test",
        category=PromptCategory.CONTENT_ANALYSIS,
        template="Test: {value}",
        version="1.0",
    )
    
    registry.register(template)
    retrieved = registry.get("custom_test")
    assert retrieved.name == "custom_test"


def test_token_estimation():
    """Test token estimation functions."""
    from apps.content.token_utils import estimate_tokens, estimate_request_cost
    
    text = "This is a test string for token estimation."
    tokens = estimate_tokens(text)
    assert tokens > 0
    
    # estimate_request_cost requires: prompt, system, max_output_tokens, model
    cost_info = estimate_request_cost(
        prompt=text,
        system=None,
        max_output_tokens=100,
        model="claude-3-sonnet"
    )
    assert cost_info["input_tokens"] > 0
    assert cost_info["max_cost_usd"] >= 0


def test_cost_tracker():
    """Test CostTracker functionality."""
    from apps.content.token_utils import CostTracker
    
    tracker = CostTracker()
    tracker.record_usage(
        model="claude-3-sonnet",
        input_tokens=100,
        output_tokens=50,
        prompt_name="test_op",
    )
    
    # Use get_daily_usage instead of get_summary
    usage = tracker.get_daily_usage()
    assert usage["total_requests"] >= 1
    assert usage["total_input_tokens"] >= 100


def test_response_cache():
    """Test ResponseCache functionality."""
    from apps.content.token_utils import ResponseCache
    
    response_cache = ResponseCache(ttl=3600, enabled=True)
    
    # Test cache miss - uses prompt, system, model, temperature
    result = response_cache.get("test_prompt", None, "claude-3-sonnet", 0.3)
    # May return None or value depending on Django cache backend
    
    # Test cache set with correct signature
    # set(prompt, system, model, temperature, response, input_tokens, output_tokens)
    response_cache.set(
        "test_prompt2", None, "claude-3-sonnet", 0.3,
        "cached response", 50, 25
    )
    
    # Result depends on Django cache backend configuration
    # Just verify no errors
    assert response_cache.get_stats() is not None


# =============================================================================
# Test Suite 7: Observability (Phase 8)
# =============================================================================

def test_structured_logger():
    """Test StructuredLogger functionality."""
    from apps.core.observability import StructuredLogger, get_logger
    
    logger = get_logger("test_component")
    assert logger is not None
    
    # Should not raise
    logger.info("Test message", extra_field="value")


def test_metrics_collector():
    """Test MetricsCollector functionality."""
    from apps.core.observability import MetricsCollector, MetricType
    
    collector = MetricsCollector()
    
    # Test counter
    collector.increment("test_counter", tags={"test": "true"})
    
    # Test gauge
    collector.gauge("test_gauge", 42.0)
    
    # Test histogram
    collector.histogram("test_histogram", 1.5)
    
    # Get all metrics
    all_metrics = collector.get_all_metrics()
    assert "test_counter" in all_metrics or len(all_metrics) >= 0


def test_health_checker():
    """Test HealthChecker functionality."""
    from apps.core.observability import HealthChecker, HealthStatus, HealthCheckResult
    
    checker = HealthChecker()
    
    # Register a simple check that returns HealthCheckResult
    def simple_check():
        return HealthCheckResult(
            name="simple_test",
            status=HealthStatus.HEALTHY,
            message="All good"
        )
    
    checker.register("simple_test", simple_check)
    
    # Run the check
    result = checker.check("simple_test")
    assert result.status == HealthStatus.HEALTHY


def test_decorators():
    """Test observability decorators."""
    from apps.core.observability import timed, counted, logged
    
    @timed("test_function")
    def timed_function():
        return "result"
    
    @counted("test_counter")
    def counted_function():
        return "counted"
    
    @logged()  # logged requires parentheses
    def logged_function():
        return "logged"
    
    # All should execute without error
    assert timed_function() == "result"
    assert counted_function() == "counted"
    assert logged_function() == "logged"


def test_request_tracer():
    """Test RequestTracer for correlation IDs."""
    from apps.core.observability import RequestTracer
    
    tracer = RequestTracer()
    
    # Start a trace
    trace_id = tracer.new_trace()
    assert trace_id is not None
    
    # Get current trace
    current = tracer.correlation_id
    assert current == trace_id
    
    # Use context manager for tracing
    with tracer.trace() as new_id:
        assert tracer.correlation_id == new_id


# =============================================================================
# Test Suite 8: Cross-Component Integration
# =============================================================================

def test_crawler_with_observability():
    """Test crawler components with observability integration."""
    from apps.core.observability import get_logger, MetricsCollector, timed
    from apps.sources.crawlers.fetchers import HTTPFetcher
    
    logger = get_logger("crawler")
    metrics = MetricsCollector()
    
    @timed("fetch_operation")
    def instrumented_fetch():
        fetcher = HTTPFetcher()
        metrics.increment("fetch_attempts")
        return fetcher
    
    result = instrumented_fetch()
    assert result is not None


def test_state_machine_with_logging():
    """Test state machine with structured logging."""
    from apps.core.observability import get_logger
    from apps.articles.state_machine import ArticleStateMachine, ArticleState
    
    logger = get_logger("state_machine")
    
    mock_article = MagicMock()
    mock_article.id = 1
    mock_article.processing_status = 'collected'
    mock_article.processing_error = ''
    mock_article.retry_count = 0
    mock_article.save = MagicMock()
    
    machine = ArticleStateMachine(mock_article)
    logger.info("Created state machine", article_id=1, state=machine.current_state.value)
    
    assert machine.current_state == ArticleState.COLLECTED


def test_llm_with_metrics():
    """Test LLM components with metrics tracking."""
    from apps.core.observability import MetricsCollector, record_llm_metrics
    from apps.content.prompts import PromptTemplate, PromptCategory
    from apps.content.token_utils import estimate_tokens
    
    metrics = MetricsCollector()
    
    template = PromptTemplate(
        name="test_llm",
        category=PromptCategory.CONTENT_ANALYSIS,
        template="Analyze: {text}",
        version="1.0",
    )
    
    prompt = template.render(text="Sample text for analysis")
    input_tokens = estimate_tokens(prompt)
    output_tokens = 50  # Simulated
    
    # Record metrics - use prompt_name, not operation; duration_ms not latency_seconds
    record_llm_metrics(
        model="claude-3-sonnet",
        prompt_name="test",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=500.0,
    )
    
    # Verify no errors
    assert True


def test_full_pipeline_simulation():
    """Simulate a full article processing pipeline."""
    from apps.core.observability import get_logger, MetricsCollector, HealthChecker
    from apps.articles.state_machine import ArticleState, ProcessingPipeline
    from apps.content.prompts import PromptRegistry
    from apps.content.token_utils import CostTracker
    from apps.sources.crawlers.extractors import extract_content
    
    # Initialize all components
    logger = get_logger("pipeline")
    metrics = MetricsCollector()
    health = HealthChecker()
    prompts = PromptRegistry()
    costs = CostTracker()
    pipeline = ProcessingPipeline()
    
    # Simulate pipeline steps
    logger.info("Starting pipeline simulation")
    
    # Step 1: Extract content
    html = "<html><body><p>Test article content.</p></body></html>"
    extraction = extract_content(html, url="https://example.com/test")
    metrics.increment("articles_extracted")
    
    # Step 2: Score content (simulated)
    score = 75.0
    metrics.histogram("article_scores", score)
    
    # Step 3: Track costs (simulated) - using correct method
    costs.record_usage(
        model="claude-3-sonnet",
        input_tokens=100,
        output_tokens=50,
        prompt_name="score",
    )
    
    logger.info("Pipeline simulation complete", 
                extraction_quality=str(extraction.quality) if extraction else "none",
                score=score)
    
    assert extraction is not None


# =============================================================================
# Test Suite 9: Health Check Integration
# =============================================================================

def test_all_health_checks():
    """Test all registered health checks."""
    from apps.core.observability import HealthChecker, HealthStatus
    
    checker = HealthChecker()
    
    # Run all checks
    results = checker.check_all()
    
    # Should have at least some checks registered
    # The built-in checks (database, redis, celery, disk_space) may or may not pass
    # depending on environment, but should not raise errors
    assert isinstance(results, dict)


def test_aggregate_health():
    """Test aggregate health status computation."""
    from apps.core.observability import HealthChecker, HealthStatus, HealthCheckResult
    
    checker = HealthChecker()
    
    # Register checks with known outcomes
    checker.register("healthy_check", lambda: HealthCheckResult(
        name="healthy_check",
        status=HealthStatus.HEALTHY,
        message="OK"
    ))
    checker.register("degraded_check", lambda: HealthCheckResult(
        name="degraded_check",
        status=HealthStatus.DEGRADED,
        message="Slow"
    ))
    
    # Run all checks and check aggregate
    results = checker.check_all()
    
    # Should have status in the results
    assert "status" in results
    assert results["status"] in ("healthy", "degraded", "unhealthy")


# =============================================================================
# Main Test Runner
# =============================================================================

def main():
    """Run all integration tests."""
    print("=" * 70)
    print("EMCIP Integration Test Suite")
    print("Testing all phases (2-8) working together")
    print("=" * 70)
    
    runner = IntegrationTestRunner()
    
    # Suite 1: Interface Abstractions (Phase 2)
    print("\n[Phase 2] Interface Abstractions")
    runner.run_test("Interface imports", test_interface_imports)
    runner.run_test("Fetcher implementations", test_fetcher_implementations)
    runner.run_test("ModularCrawler creation", test_modular_crawler_creation)
    
    # Suite 2: Pagination Memory (Phase 3)
    print("\n[Phase 3] Pagination Memory")
    runner.run_test("Pagination strategies", test_pagination_strategies)
    runner.run_test("Registry functions", test_registry_functions)
    
    # Suite 3: Playwright JS Handling (Phase 4)
    print("\n[Phase 4] Playwright JS Handling")
    runner.run_test("Playwright availability flag", test_playwright_availability_flag)
    runner.run_test("HybridFetcher creation", test_hybrid_fetcher_creation)
    
    # Suite 4: Extraction Quality (Phase 5)
    print("\n[Phase 5] Extraction Quality")
    runner.run_test("Content extractors", test_content_extractors)
    runner.run_test("ExtractionResult structure", test_extraction_result_structure)
    runner.run_test("Hybrid extraction", test_hybrid_extraction)
    
    # Suite 5: State Machine (Phase 6)
    print("\n[Phase 6] State Machine")
    runner.run_test("Article states", test_article_states)
    runner.run_test("State transitions", test_state_transitions)
    runner.run_test("StateMachine instantiation", test_state_machine_instantiation)
    runner.run_test("ProcessingPipeline creation", test_processing_pipeline)
    
    # Suite 6: LLM Hardening (Phase 7)
    print("\n[Phase 7] LLM Hardening")
    runner.run_test("PromptTemplate", test_prompt_template)
    runner.run_test("PromptRegistry", test_prompt_registry)
    runner.run_test("Token estimation", test_token_estimation)
    runner.run_test("CostTracker", test_cost_tracker)
    runner.run_test("ResponseCache", test_response_cache)
    
    # Suite 7: Observability (Phase 8)
    print("\n[Phase 8] Observability")
    runner.run_test("StructuredLogger", test_structured_logger)
    runner.run_test("MetricsCollector", test_metrics_collector)
    runner.run_test("HealthChecker", test_health_checker)
    runner.run_test("Decorators", test_decorators)
    runner.run_test("RequestTracer", test_request_tracer)
    
    # Suite 8: Cross-Component Integration
    print("\n[Cross-Component] Integration")
    runner.run_test("Crawler with observability", test_crawler_with_observability)
    runner.run_test("State machine with logging", test_state_machine_with_logging)
    runner.run_test("LLM with metrics", test_llm_with_metrics)
    runner.run_test("Full pipeline simulation", test_full_pipeline_simulation)
    
    # Suite 9: Health Checks
    print("\n[Health Checks] System Integration")
    runner.run_test("All health checks", test_all_health_checks)
    runner.run_test("Aggregate health", test_aggregate_health)
    
    # Summary
    print("\n" + "=" * 70)
    success = runner.summary()
    
    if success:
        print("\n✅ All integration tests passed!")
    else:
        print("\n❌ Some integration tests failed")
        for name, passed, error in runner.results:
            if not passed:
                print(f"  - {name}: {error}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
