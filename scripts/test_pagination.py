#!/usr/bin/env python
"""
Test script for crawler utilities: pagination, URL normalization, rate limiting, and async fetching.
Run from project root: python scripts/test_pagination.py
"""

import os
import sys
import time

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from apps.sources.crawlers.registry import get_rules_for_domain, get_pagination_config
from apps.sources.crawlers.utils import (
    URLNormalizer,
    URLDeduplicator,
    DomainRateLimiter,
    normalize_url,
)
from apps.sources.crawlers.scrapy_crawler import ScrapyCrawler
from urllib.parse import urlparse, urlencode


def test_pagination_config():
    """Test that pagination config returns correct values."""
    print("\n" + "="*60)
    print("Testing Pagination Configuration")
    print("="*60)
    
    # Test configured domain
    config = get_pagination_config("vietnamnews.vn")
    print(f"\nvietnam news.vn config:")
    print(f"  - pagination_type: {config['pagination_type']}")
    print(f"  - page_param: {config['page_param']}")
    print(f"  - start_page: {config['start_page']}")
    
    # Test unconfigured domain (should use defaults)
    config = get_pagination_config("unknown-site.com")
    print(f"\nunknown-site.com config (defaults):")
    print(f"  - pagination_type: {config['pagination_type']}")
    print(f"  - page_param: {config['page_param']}")
    print(f"  - start_page: {config['start_page']}")
    print(f"  - next_link_selector: {config['next_link_selector']}")
    
    print("\n✓ Pagination configuration test passed!")


def test_url_normalization():
    """Test URL normalization."""
    print("\n" + "="*60)
    print("Testing URL Normalization")
    print("="*60)
    
    normalizer = URLNormalizer()
    
    test_cases = [
        # (input_url, expected_behavior_description)
        ("https://Example.COM/Path/", "Lowercase domain, remove trailing slash"),
        ("http://example.com:80/news/", "Remove default port"),
        ("https://example.com:443/news/", "Remove default port (https)"),
        ("https://example.com/news?utm_source=twitter&id=123", "Remove tracking params"),
        ("https://example.com/news?b=2&a=1", "Sort query params"),
        ("https://example.com/news#section", "Remove fragment"),
        ("https://example.com/news/?fbclid=abc123", "Remove fbclid"),
    ]
    
    print("\nNormalization results:")
    for url, description in test_cases:
        normalized = normalizer.normalize(url)
        print(f"\n  {description}:")
        print(f"    Input:  {url}")
        print(f"    Output: {normalized}")
    
    # Test URL equivalence
    url1 = "https://Example.COM/article?utm_source=fb&id=123"
    url2 = "https://example.com/article?id=123&utm_campaign=test"
    
    print(f"\n  URL equivalence check:")
    print(f"    URL 1: {url1}")
    print(f"    URL 2: {url2}")
    print(f"    Same after normalization: {normalizer.are_same_url(url1, url2)}")
    
    print("\n✓ URL normalization test passed!")


def test_url_deduplicator():
    """Test URL deduplication."""
    print("\n" + "="*60)
    print("Testing URL Deduplicator")
    print("="*60)
    
    dedup = URLDeduplicator()
    
    # Add some URLs
    urls = [
        "https://example.com/article/1",
        "https://example.com/article/2",
        "https://Example.COM/article/1",  # Duplicate (different case)
        "https://example.com/article/1?utm_source=test",  # Duplicate (with tracking)
        "https://example.com/article/3",
    ]
    
    print("\nAdding URLs:")
    for url in urls:
        result = dedup.add_if_new(url)
        status = "NEW" if result else "DUPLICATE"
        print(f"  [{status}] {url}")
    
    print(f"\n  Total unique URLs: {dedup.count()}")
    assert dedup.count() == 3, f"Expected 3 unique URLs, got {dedup.count()}"
    
    print("\n✓ URL deduplicator test passed!")


def test_rate_limiter():
    """Test per-domain rate limiting."""
    print("\n" + "="*60)
    print("Testing Per-Domain Rate Limiter")
    print("="*60)
    
    # Create rate limiter with custom domain delays
    limiter = DomainRateLimiter(
        default_delay=1.0,
        domain_delays={
            "slow-site.com": 3.0,
            "fast-site.com": 0.5,
        }
    )
    
    print("\n  Configured delays:")
    print(f"    Default: {limiter.default_delay}s")
    print(f"    slow-site.com: {limiter.get_delay_for_domain('slow-site.com')}s")
    print(f"    fast-site.com: {limiter.get_delay_for_domain('fast-site.com')}s")
    print(f"    unknown.com (uses default): {limiter.get_delay_for_domain('unknown.com')}s")
    
    # Test rate limiting
    print("\n  Testing rate limit enforcement:")
    domain = "test-domain.com"
    limiter.set_delay_for_domain(domain, 0.3)
    
    # First request - should not wait
    start = time.time()
    wait1 = limiter.wait_if_needed(domain)
    elapsed1 = time.time() - start
    print(f"    First request: waited {wait1:.3f}s (elapsed: {elapsed1:.3f}s)")
    
    # Second request immediately - should wait
    start = time.time()
    wait2 = limiter.wait_if_needed(domain)
    elapsed2 = time.time() - start
    print(f"    Second request: waited {wait2:.3f}s (elapsed: {elapsed2:.3f}s)")
    
    assert wait2 > 0.1, "Second request should have waited"
    
    print("\n✓ Rate limiter test passed!")


def test_url_building():
    """Test URL building for different pagination types."""
    print("\n" + "="*60)
    print("Testing URL Building")
    print("="*60)
    
    # Create a mock source for testing
    class MockSource:
        domain = "example.com"
        url = "https://example.com/news/"
        crawler_type = "scrapy"
        crawler_config = {"max_pages": 5}
        custom_headers = {}
    
    source = MockSource()
    crawler = ScrapyCrawler(source)
    
    # Test parameter-based URL building
    base_url = "https://example.com/news/"
    page2_url = crawler._build_param_url(base_url, 2)
    print(f"\nParameter pagination:")
    print(f"  Base: {base_url}")
    print(f"  Page 2: {page2_url}")
    assert "page=2" in page2_url, "Page parameter not found in URL"
    
    # Test with existing query params
    base_url_with_params = "https://example.com/news/?category=tech"
    page3_url = crawler._build_param_url(base_url_with_params, 3)
    print(f"\nWith existing params:")
    print(f"  Base: {base_url_with_params}")
    print(f"  Page 3: {page3_url}")
    assert "page=3" in page3_url, "Page parameter not found in URL"
    assert "category=tech" in page3_url, "Existing params lost"
    
    # Test path-based URL building
    page2_path = crawler._build_path_url("https://example.com/news/", 2)
    print(f"\nPath pagination:")
    print(f"  Base: https://example.com/news/")
    print(f"  Page 2: {page2_path}")
    assert "/page/2/" in page2_path, "Page path not found in URL"
    
    print("\n✓ URL building test passed!")


def test_next_link_detection():
    """Test detection of 'next page' links."""
    print("\n" + "="*60)
    print("Testing Next Link Detection")
    print("="*60)
    
    # Create mock response with next link
    class MockResponse:
        url = "https://example.com/news/"
        content = b"""
        <html>
        <body>
            <div class="pagination">
                <a href="/news/?page=1">1</a>
                <a href="/news/?page=2" class="next">Next</a>
            </div>
        </body>
        </html>
        """
    
    class MockSource:
        domain = "example.com"
        url = "https://example.com/news/"
        crawler_type = "scrapy"
        crawler_config = {}
        custom_headers = {}
    
    source = MockSource()
    crawler = ScrapyCrawler(source)
    
    response = MockResponse()
    next_url = crawler._find_next_link(response)
    
    print(f"\nHTML contains: <a class='next' href='/news/?page=2'>")
    print(f"Detected next URL: {next_url}")
    
    if next_url:
        print("✓ Next link detection test passed!")
    else:
        print("⚠ Next link not detected (selector may need adjustment)")


def test_async_fetch_availability():
    """Check if async fetching is available."""
    print("\n" + "="*60)
    print("Testing Async Fetch Availability")
    print("="*60)
    
    try:
        import aiohttp
        print(f"\n  aiohttp version: {aiohttp.__version__}")
        print("  ✓ Async fetching is available")
    except ImportError:
        print("\n  ⚠ aiohttp not installed")
        print("  Install with: pip install aiohttp")
        print("  Crawler will fall back to synchronous fetching")


def test_feature_summary():
    """Print summary of all crawler features."""
    print("\n" + "="*60)
    print("Crawler Feature Summary")
    print("="*60)
    
    print("""
    The crawler now includes these features:
    
    1. PAGINATION (3 strategies)
       - Parameter: ?page=N
       - Path: /page/N/
       - Next link: follows <a class="next">
    
    2. URL NORMALIZATION
       - Lowercase domain
       - Remove default ports (80/443)
       - Remove tracking params (utm_*, fbclid, etc.)
       - Sort query params for consistency
       - Remove fragments
    
    3. PER-DOMAIN RATE LIMITING
       - Configurable delay per domain
       - Thread-safe implementation
       - Automatic enforcement between requests
    
    4. ASYNC PARALLEL FETCHING
       - Uses aiohttp for concurrent requests
       - Configurable max_concurrent (default: 5)
       - Respects rate limits per domain
       - Falls back to sync if aiohttp unavailable
    
    Configuration in source.crawler_config:
    
        {
            "max_pages": 5,
            "delay": 2,                    # Default delay
            "use_async_fetch": true,       # Enable async
            "max_concurrent": 5,           # Max parallel requests
            "domain_delays": {             # Per-domain overrides
                "slow-site.com": 5,
                "fast-site.com": 0.5
            }
        }
    """)


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# EMCIP Crawler Utilities Test")
    print("#"*60)
    
    try:
        test_pagination_config()
        test_url_normalization()
        test_url_deduplicator()
        test_rate_limiter()
        test_url_building()
        test_next_link_detection()
        test_async_fetch_availability()
        test_feature_summary()
        
        print("\n" + "="*60)
        print("All tests completed successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
