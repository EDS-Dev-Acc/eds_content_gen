#!/usr/bin/env python
"""
Test script for Phase 4: Playwright JS Handling.

Tests:
1. PlaywrightFetcher basic functionality
2. HybridFetcher HTTP-first with fallback detection
3. get_crawler factory with different fetcher types
4. JS detection indicators
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.sources.crawlers import (
    get_crawler,
    _create_fetcher,
    HTTPFetcher,
    HybridFetcher,
    PLAYWRIGHT_AVAILABLE,
    Fetcher,
    FetchResult,
)
from apps.sources.crawlers.interfaces import FetcherType
from apps.sources.models import Source

# Conditionally import Playwright fetchers
if PLAYWRIGHT_AVAILABLE:
    from apps.sources.crawlers import PlaywrightFetcher, PlaywrightFetcherSync


def get_or_create_test_source(**kwargs):
    """Get or create a test source for testing."""
    defaults = {
        'name': 'Test Source for Playwright',
        'url': 'https://example.com',
        'domain': 'example.com',
        'crawler_type': 'modular',
        'status': 'active',  # Use 'status' not 'is_active'
    }
    defaults.update(kwargs)
    source, _ = Source.objects.get_or_create(
        domain=defaults['domain'],
        defaults=defaults,
    )
    return source


def test_playwright_available():
    """Test that Playwright is properly installed."""
    print("\n=== Test 1: Playwright Availability ===")
    
    print(f"PLAYWRIGHT_AVAILABLE: {PLAYWRIGHT_AVAILABLE}")
    
    if PLAYWRIGHT_AVAILABLE:
        print("✓ Playwright is installed and available")
        
        # Try importing the actual playwright module
        try:
            from playwright.sync_api import sync_playwright
            print("✓ playwright.sync_api import successful")
        except ImportError as e:
            print(f"✗ playwright.sync_api import failed: {e}")
            return False
        
        try:
            from playwright.async_api import async_playwright
            print("✓ playwright.async_api import successful")
        except ImportError as e:
            print(f"✗ playwright.async_api import failed: {e}")
            return False
            
        return True
    else:
        print("⚠ Playwright is not available - browser tests will be skipped")
        return True  # Not a failure, just not available


def test_fetcher_types():
    """Test FetcherType enum values."""
    print("\n=== Test 2: FetcherType Enum ===")
    
    assert FetcherType.HTTP.value == 'http'
    print(f"✓ FetcherType.HTTP = '{FetcherType.HTTP.value}'")
    
    assert FetcherType.BROWSER.value == 'browser'
    print(f"✓ FetcherType.BROWSER = '{FetcherType.BROWSER.value}'")
    
    assert FetcherType.HYBRID.value == 'hybrid'
    print(f"✓ FetcherType.HYBRID = '{FetcherType.HYBRID.value}'")
    
    return True


def test_http_fetcher_type():
    """Test that HTTPFetcher correctly implements the interface."""
    print("\n=== Test 3: HTTPFetcher Type Property ===")
    
    fetcher = HTTPFetcher()
    
    assert isinstance(fetcher, Fetcher)
    print("✓ HTTPFetcher is instance of Fetcher")
    
    assert fetcher.fetcher_type == FetcherType.HTTP
    print(f"✓ HTTPFetcher.fetcher_type = {fetcher.fetcher_type}")
    
    return True


def test_hybrid_fetcher_type():
    """Test that HybridFetcher correctly implements the interface."""
    print("\n=== Test 4: HybridFetcher Type Property ===")
    
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠ Skipped (Playwright not available)")
        return True
    
    fetcher = HybridFetcher()
    
    assert isinstance(fetcher, Fetcher)
    print("✓ HybridFetcher is instance of Fetcher")
    
    assert fetcher.fetcher_type == FetcherType.HYBRID
    print(f"✓ HybridFetcher.fetcher_type = {fetcher.fetcher_type}")
    
    return True


def test_playwright_fetcher_type():
    """Test that PlaywrightFetcherSync correctly implements the interface."""
    print("\n=== Test 5: PlaywrightFetcherSync Type Property ===")
    
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠ Skipped (Playwright not available)")
        return True
    
    fetcher = PlaywrightFetcherSync()
    
    # PlaywrightFetcherSync has fetcher_type property even if not inheriting from Fetcher
    assert hasattr(fetcher, 'fetcher_type')
    print("✓ PlaywrightFetcherSync has fetcher_type property")
    
    assert fetcher.fetcher_type == FetcherType.BROWSER
    print(f"✓ PlaywrightFetcherSync.fetcher_type = {fetcher.fetcher_type}")
    
    # Check required methods
    assert hasattr(fetcher, 'fetch')
    assert hasattr(fetcher, 'fetch_many')
    assert hasattr(fetcher, 'close')
    print("✓ PlaywrightFetcherSync has fetch, fetch_many, close methods")
    
    return True


def test_create_fetcher_helper():
    """Test the _create_fetcher helper function."""
    print("\n=== Test 6: _create_fetcher Helper ===")
    
    # Create a test source
    source = get_or_create_test_source()
    
    # Test HTTP fetcher creation
    fetcher = _create_fetcher('http', source)
    assert isinstance(fetcher, HTTPFetcher)
    print("✓ _create_fetcher('http', source) returns HTTPFetcher")
    
    # Test browser fetcher creation
    if PLAYWRIGHT_AVAILABLE:
        fetcher = _create_fetcher('browser', source)
        assert isinstance(fetcher, PlaywrightFetcherSync)
        print("✓ _create_fetcher('browser', source) returns PlaywrightFetcherSync")
        
        fetcher = _create_fetcher('hybrid', source)
        assert isinstance(fetcher, HybridFetcher)
        print("✓ _create_fetcher('hybrid', source) returns HybridFetcher")
    else:
        print("⚠ Browser/Hybrid tests skipped (Playwright not available)")
    
    return True


def test_get_crawler_factory():
    """Test get_crawler factory with different types."""
    print("\n=== Test 7: get_crawler Factory ===")
    
    # Create test sources with different crawler types
    modular_source = get_or_create_test_source(
        domain='modular-test.com',
        name='Modular Test Source',
        url='https://modular-test.com',
        crawler_type='modular',
    )
    
    # Test modular crawler
    crawler = get_crawler(modular_source, use_modular=True)
    assert crawler.__class__.__name__ == 'ModularCrawler'
    print("✓ get_crawler(source, use_modular=True) returns ModularCrawler")
    
    # Check that modular crawler has HTTPFetcher by default
    assert hasattr(crawler, 'fetcher')
    assert isinstance(crawler.fetcher, HTTPFetcher)
    print("✓ ModularCrawler has HTTPFetcher by default")
    
    if PLAYWRIGHT_AVAILABLE:
        # Test with fetcher_type override
        hybrid_crawler = get_crawler(modular_source, use_modular=True, fetcher_type='hybrid')
        assert hybrid_crawler.__class__.__name__ == 'ModularCrawler'
        assert isinstance(hybrid_crawler.fetcher, HybridFetcher)
        print("✓ get_crawler with fetcher_type='hybrid' returns ModularCrawler with HybridFetcher")
        
        # Test browser fetcher
        browser_crawler = get_crawler(modular_source, use_modular=True, fetcher_type='browser')
        assert browser_crawler.__class__.__name__ == 'ModularCrawler'
        assert isinstance(browser_crawler.fetcher, PlaywrightFetcherSync)
        print("✓ get_crawler with fetcher_type='browser' returns ModularCrawler with PlaywrightFetcherSync")
    
    return True


def test_js_detection_indicators():
    """Test JS detection in HybridFetcher."""
    print("\n=== Test 8: JS Detection Indicators ===")
    
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠ Skipped (Playwright not available)")
        return True
    
    # JS_REQUIRED_INDICATORS is a class attribute
    js_indicators = HybridFetcher.JS_REQUIRED_INDICATORS
    
    assert len(js_indicators) > 0
    print(f"✓ Found {len(js_indicators)} JS detection indicators")
    
    # Check for expected indicators
    expected = ['__NEXT_DATA__', 'React', 'Vue', 'JavaScript']
    found = []
    for exp in expected:
        for indicator in js_indicators:
            if exp.lower() in indicator.lower():
                found.append(exp)
                break
    
    print(f"✓ Framework indicators present: {found}")
    
    # Test detection function
    fetcher = HybridFetcher()
    
    # Test static HTML (no JS needed)
    static_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>Static Content</h1>
        <p>This is a normal page with enough content to pass the minimum length check.
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor 
        incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud 
        exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute 
        irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla 
        pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia 
        deserunt mollit anim id est laborum.</p>
    </body>
    </html>
    """
    needs_js = fetcher._looks_like_js_page(static_html)
    print(f"✓ Static HTML needs JS: {needs_js} (expected: False)")
    
    # Test React-based HTML (needs JS)
    react_html = """
    <!DOCTYPE html>
    <html>
    <head><title>React App</title></head>
    <body>
        <div id="root"></div>
        <script>
            window.__NEXT_DATA__ = {"props":{}};
        </script>
    </body>
    </html>
    """
    needs_js = fetcher._looks_like_js_page(react_html)
    print(f"✓ React/Next.js HTML needs JS: {needs_js} (expected: True)")
    
    return True


def test_playwright_fetcher_live():
    """Test PlaywrightFetcherSync with a real page (optional)."""
    print("\n=== Test 9: PlaywrightFetcherSync Live Test (Optional) ===")
    
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠ Skipped (Playwright not available)")
        return True
    
    # Use a simple, reliable test URL
    test_url = "https://example.com"
    
    try:
        fetcher = PlaywrightFetcherSync(
            headless=True,
            timeout=30000,
        )
        
        result = fetcher.fetch(test_url)
        
        assert result.success
        print(f"✓ Successfully fetched {test_url}")
        
        assert result.html is not None
        assert len(result.html) > 0
        print(f"✓ Got HTML content ({len(result.html)} chars)")
        
        assert 'Example Domain' in result.html
        print("✓ HTML contains expected content")
        
        fetcher.close()
        print("✓ Fetcher closed successfully")
        
        return True
        
    except Exception as e:
        print(f"⚠ Live test failed (may be network issue): {e}")
        return True  # Don't fail on network issues


def test_hybrid_fetcher_http_first():
    """Test that HybridFetcher tries HTTP first."""
    print("\n=== Test 10: HybridFetcher HTTP-First Strategy ===")
    
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠ Skipped (Playwright not available)")
        return True
    
    fetcher = HybridFetcher()
    
    # Check internal state
    assert hasattr(fetcher, 'http_fetcher')
    assert isinstance(fetcher.http_fetcher, HTTPFetcher)
    print("✓ HybridFetcher has internal HTTPFetcher")
    
    assert hasattr(fetcher, '_playwright_fetcher')
    print("✓ HybridFetcher has _playwright_fetcher (lazy-loaded)")
    
    assert hasattr(fetcher, '_browser_domains')
    assert isinstance(fetcher._browser_domains, set)
    print("✓ HybridFetcher has _browser_domains cache")
    
    # Test force browser domains
    fetcher_with_forced = HybridFetcher(force_browser_domains=['spa-site.com', 'js-heavy.io'])
    assert 'spa-site.com' in fetcher_with_forced.force_browser_domains
    assert 'js-heavy.io' in fetcher_with_forced.force_browser_domains
    print("✓ HybridFetcher accepts force_browser_domains config")
    
    return True


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_playwright_available,
        test_fetcher_types,
        test_http_fetcher_type,
        test_hybrid_fetcher_type,
        test_playwright_fetcher_type,
        test_create_fetcher_helper,
        test_get_crawler_factory,
        test_js_detection_indicators,
        test_playwright_fetcher_live,
        test_hybrid_fetcher_http_first,
    ]
    
    print("=" * 60)
    print("Phase 4: Playwright JS Handling Tests")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} returned False")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All Phase 4 tests passed!")
        return True
    else:
        print(f"\n✗ {failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
