#!/usr/bin/env python
"""
Test script for Phase 7: LLM Hardening.

Tests:
1. Prompt templates and registry
2. Token counting and limits
3. Cost tracking
4. Response caching
5. ClaudeClient integration
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.content.prompts import (
    PromptTemplate,
    PromptCategory,
    PromptRegistry,
    prompt_registry,
    AI_DETECTION_V1,
    AI_DETECTION_V2,
)
from apps.content.token_utils import (
    estimate_tokens,
    truncate_to_tokens,
    check_within_limit,
    get_model_limit,
    CostTracker,
    ResponseCache,
    UsageRecord,
    MODEL_PRICING,
)
from apps.content.llm import ClaudeClient, parse_llm_json


def test_prompt_template_basic():
    """Test PromptTemplate creation and rendering."""
    print("\n=== Test 1: PromptTemplate Basic ===")
    
    template = PromptTemplate(
        name="test_template",
        category=PromptCategory.AI_DETECTION,
        template="Analyze this text: {text}\nReturn: {format}",
        system_prompt="You are a {role}.",
        version="1.0",
        description="Test template",
    )
    
    # Test render
    rendered = template.render(text="Hello world", format="JSON")
    assert "Hello world" in rendered
    assert "JSON" in rendered
    print(f"  Rendered: {rendered[:50]}...")
    
    # Test system prompt render
    system = template.get_system_prompt(role="test assistant")
    assert system == "You are a test assistant."
    print(f"  System: {system}")
    
    # Test missing variable
    try:
        template.render(text="Hello")  # Missing 'format'
        assert False, "Should raise ValueError"
    except ValueError as e:
        print(f"  Missing var correctly caught: {e}")
    
    print("  PASSED")
    return True


def test_prompt_registry():
    """Test PromptRegistry functionality."""
    print("\n=== Test 2: PromptRegistry ===")
    
    # Create fresh registry for testing
    registry = PromptRegistry.__new__(PromptRegistry)
    registry._templates = {}
    registry._active_versions = {}
    
    # Register templates
    t1 = PromptTemplate(
        name="my_prompt",
        category=PromptCategory.SCORING,
        template="Score: {text}",
        version="1.0",
    )
    t2 = PromptTemplate(
        name="my_prompt",
        category=PromptCategory.SCORING,
        template="Enhanced Score: {text}",
        version="2.0",
    )
    
    registry.register(t1, active=True)
    registry.register(t2, active=False)
    
    # Get active version
    active = registry.get("my_prompt")
    assert active.version == "1.0"
    print(f"  Active version: {active.version}")
    
    # Get specific version
    v2 = registry.get("my_prompt", version="2.0")
    assert v2.version == "2.0"
    print(f"  Specific version: {v2.version}")
    
    # List versions
    versions = registry.get_all_versions("my_prompt")
    assert "1.0" in versions and "2.0" in versions
    print(f"  All versions: {versions}")
    
    # Set active version
    registry.set_active_version("my_prompt", "2.0")
    active = registry.get("my_prompt")
    assert active.version == "2.0"
    print(f"  New active: {active.version}")
    
    print("  PASSED")
    return True


def test_default_prompts_registered():
    """Test that default prompts are registered."""
    print("\n=== Test 3: Default Prompts Registered ===")
    
    # Re-register defaults to ensure they're present
    from apps.content.prompts import register_default_prompts
    register_default_prompts()
    
    # Check AI detection templates
    ai_v1 = prompt_registry.get("ai_detection", version="1.0")
    ai_v2 = prompt_registry.get("ai_detection", version="2.0")
    
    assert ai_v1 is not None, "AI Detection v1 not found"
    assert ai_v2 is not None, "AI Detection v2 not found"
    print(f"  AI Detection v1: {ai_v1.description[:40]}...")
    print(f"  AI Detection v2: {ai_v2.description[:40]}...")
    
    # Check other templates
    templates = prompt_registry.list_templates()
    assert len(templates) >= 5, f"Expected at least 5 templates, got {len(templates)}"
    print(f"  Total templates: {len(templates)}")
    print(f"  Templates: {templates}")
    
    print("  PASSED")
    return True


def test_token_estimation():
    """Test token counting utilities."""
    print("\n=== Test 4: Token Estimation ===")
    
    # Basic estimation
    short_text = "Hello world"
    tokens = estimate_tokens(short_text)
    assert 2 <= tokens <= 10
    print(f"  '{short_text}' = {tokens} tokens")
    
    # Longer text
    long_text = "This is a longer text " * 100
    tokens = estimate_tokens(long_text)
    assert 400 <= tokens <= 800
    print(f"  Long text ({len(long_text)} chars) = {tokens} tokens")
    
    # Empty text
    assert estimate_tokens("") == 0
    print(f"  Empty text = 0 tokens")
    
    print("  PASSED")
    return True


def test_token_truncation():
    """Test token truncation."""
    print("\n=== Test 5: Token Truncation ===")
    
    long_text = "This is a test sentence. " * 1000
    
    # Truncate to 100 tokens
    truncated = truncate_to_tokens(long_text, 100)
    truncated_tokens = estimate_tokens(truncated)
    
    assert truncated_tokens < 120  # Should be close to 100
    assert truncated.endswith("...")
    print(f"  Original: {len(long_text)} chars, ~{estimate_tokens(long_text)} tokens")
    print(f"  Truncated: {len(truncated)} chars, ~{truncated_tokens} tokens")
    
    # Short text should not be truncated
    short_text = "Hello world"
    not_truncated = truncate_to_tokens(short_text, 100)
    assert not_truncated == short_text
    print(f"  Short text unchanged: '{not_truncated}'")
    
    print("  PASSED")
    return True


def test_model_limits():
    """Test model limit checking."""
    print("\n=== Test 6: Model Limits ===")
    
    # Check known model limits
    claude_limit = get_model_limit("claude-sonnet-4-20250514")
    assert claude_limit == 200000
    print(f"  Claude Sonnet 4 limit: {claude_limit:,}")
    
    gpt4_limit = get_model_limit("gpt-4")
    assert gpt4_limit == 8192
    print(f"  GPT-4 limit: {gpt4_limit:,}")
    
    # Check within limit
    prompt = "Test prompt " * 10
    fits, input_tokens, available = check_within_limit(
        prompt, "You are a helper.", 1000, "claude-sonnet-4-20250514"
    )
    assert fits
    assert available > 1000
    print(f"  Check within limit: fits={fits}, input={input_tokens}, available={available:,}")
    
    print("  PASSED")
    return True


def test_cost_calculation():
    """Test cost calculation."""
    print("\n=== Test 7: Cost Calculation ===")
    
    # Calculate cost for Claude Sonnet 4
    cost = CostTracker.calculate_cost(
        model="claude-sonnet-4-20250514",
        input_tokens=1000,
        output_tokens=500,
    )
    
    # Expected: (1000/1M * $3) + (500/1M * $15) = $0.003 + $0.0075 = $0.0105
    assert 0.01 <= cost <= 0.02
    print(f"  1000 input + 500 output = ${cost:.4f}")
    
    # Cached should be free
    cached_cost = CostTracker.calculate_cost(
        model="claude-sonnet-4-20250514",
        input_tokens=1000,
        output_tokens=500,
        cached=True,
    )
    assert cached_cost == 0.0
    print(f"  Cached response cost: ${cached_cost:.4f}")
    
    # Check pricing exists
    assert "claude-sonnet-4-20250514" in MODEL_PRICING
    print(f"  Pricing available for {len(MODEL_PRICING)} models")
    
    print("  PASSED")
    return True


def test_cost_tracker():
    """Test CostTracker usage recording."""
    print("\n=== Test 8: CostTracker ===")
    
    # Create a fresh tracker for testing
    tracker = CostTracker.__new__(CostTracker)
    tracker._records = []
    tracker._daily_budget = 10.0
    tracker._alert_threshold = 0.8
    
    # Record some usage
    record1 = tracker.record_usage(
        model="claude-sonnet-4-20250514",
        input_tokens=1000,
        output_tokens=500,
        prompt_name="test_prompt",
    )
    
    assert record1.cost_usd > 0
    assert record1.prompt_name == "test_prompt"
    print(f"  Record 1: {record1.input_tokens}+{record1.output_tokens} = ${record1.cost_usd:.4f}")
    
    # Record cached usage
    record2 = tracker.record_usage(
        model="claude-sonnet-4-20250514",
        input_tokens=1000,
        output_tokens=500,
        cached=True,
    )
    assert record2.cost_usd == 0.0
    print(f"  Record 2 (cached): ${record2.cost_usd:.4f}")
    
    # Get daily usage
    usage = tracker.get_daily_usage()
    assert usage["total_requests"] == 2
    assert usage["cached_requests"] == 1
    print(f"  Daily usage: {usage['total_requests']} requests, ${usage['total_cost_usd']:.4f}")
    
    print("  PASSED")
    return True


def test_response_cache():
    """Test ResponseCache functionality."""
    print("\n=== Test 9: Response Cache ===")
    
    # Use in-memory cache simulation (Django cache may not be configured)
    cache = ResponseCache(ttl=60, enabled=True)
    cache.clear_stats()
    
    prompt = "Test prompt for cache"
    system = "Test system"
    model = "claude-sonnet-4-20250514"
    temperature = 0.3
    
    # Cache miss - may or may not work depending on Django cache config
    result = cache.get(prompt, system, model, temperature)
    # Just log the result, don't assert since cache backend may vary
    print(f"  Initial get result: {result}")
    
    # Test stats tracking works
    stats = cache.get_stats()
    print(f"  Stats after get: {stats}")
    
    # High temperature should not cache
    cache._stats = {"hits": 0, "misses": 0}
    high_temp_result = cache.get(prompt, system, model, 0.9)
    assert high_temp_result is None, "High temperature should not return cached value"
    # Stats should not change for high temp (we return early)
    print(f"  High temperature (0.9) correctly skipped")
    
    # Test cache key generation doesn't error
    from apps.content.token_utils import _cache_key
    key = _cache_key(prompt, system, model, temperature)
    assert key.startswith("llm_cache:")
    print(f"  Cache key format: {key[:30]}...")
    
    print("  PASSED")
    return True


def test_parse_llm_json():
    """Test JSON parsing from LLM responses."""
    print("\n=== Test 10: parse_llm_json ===")
    
    # Plain JSON
    result = parse_llm_json('{"ai": true, "confidence": 0.85}')
    assert result["ai"] == True
    print(f"  Plain JSON: {result}")
    
    # JSON with markdown fences
    result = parse_llm_json('```json\n{"ai": false, "confidence": 0.2}\n```')
    assert result["ai"] == False
    print(f"  Fenced JSON: {result}")
    
    # Invalid JSON
    result = parse_llm_json("This is not JSON")
    assert result is None
    print(f"  Invalid JSON: {result}")
    
    # Empty
    result = parse_llm_json("")
    assert result is None
    print(f"  Empty: {result}")
    
    print("  PASSED")
    return True


def test_claude_client_init():
    """Test ClaudeClient initialization."""
    print("\n=== Test 11: ClaudeClient Init ===")
    
    client = ClaudeClient(
        enable_cache=True,
        enable_cost_tracking=True,
    )
    
    assert client.model is not None
    assert client.enable_cache == True
    assert client.enable_cost_tracking == True
    print(f"  Model: {client.model}")
    print(f"  Cache enabled: {client.enable_cache}")
    print(f"  Cost tracking: {client.enable_cost_tracking}")
    print(f"  Available: {client.available}")
    
    print("  PASSED")
    return True


def test_claude_client_template():
    """Test ClaudeClient template lookup (without API call)."""
    print("\n=== Test 12: ClaudeClient Template Lookup ===")
    
    # Ensure defaults are registered
    from apps.content.prompts import register_default_prompts
    register_default_prompts()
    
    client = ClaudeClient()
    
    # Test that template exists
    template = prompt_registry.get("ai_detection")
    assert template is not None, "ai_detection template not found"
    print(f"  Template found: {template.name} v{template.version}")
    
    # Test template rendering
    rendered = template.render(text="Sample text for analysis")
    assert "Sample text for analysis" in rendered
    print(f"  Rendered length: {len(rendered)} chars")
    
    # Test missing template handling
    try:
        client.run_template("nonexistent_template", {"text": "test"})
        assert False, "Should raise ValueError"
    except ValueError as e:
        print(f"  Missing template error: {e}")
    
    print("  PASSED")
    return True


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_prompt_template_basic,
        test_prompt_registry,
        test_default_prompts_registered,
        test_token_estimation,
        test_token_truncation,
        test_model_limits,
        test_cost_calculation,
        test_cost_tracker,
        test_response_cache,
        test_parse_llm_json,
        test_claude_client_init,
        test_claude_client_template,
    ]
    
    print("=" * 60)
    print("Phase 7: LLM Hardening Tests")
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
        print("\nAll Phase 7 tests passed!")
        return True
    else:
        print(f"\n{failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
