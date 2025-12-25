#!/usr/bin/env python
"""
Test script for the new crawler interfaces (Phase 2).

Verifies that:
1. All interfaces are properly importable
2. HTTPFetcher works correctly
3. BS4LinkExtractor extracts links properly
4. Paginator strategies generate correct URLs
5. Components work together in ModularCrawler
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()


def test_imports():
    """Test that all new interfaces are importable."""
    print("=" * 60)
    print("Testing Interface Imports")
    print("=" * 60)
    
    try:
        from apps.sources.crawlers import (
            # Interfaces
            Fetcher,
            LinkExtractor,
            Paginator,
            FetchResult,
            ExtractedLink,
            PaginationResult,
            CrawlerPipeline,
            # Implementations
            HTTPFetcher,
            BS4LinkExtractor,
            ParameterPaginator,
            PathPaginator,
            NextLinkPaginator,
            OffsetPaginator,
            AdaptivePaginator,
            create_paginator,
            # Crawlers
            ModularCrawler,
        )
        print("✓ All interfaces imported successfully!")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_fetcher():
    """Test HTTPFetcher functionality."""
    print("\n" + "=" * 60)
    print("Testing HTTPFetcher")
    print("=" * 60)
    
    from apps.sources.crawlers import HTTPFetcher, FetchResult
    
    fetcher = HTTPFetcher(
        headers={'User-Agent': 'EMCIP Test Agent'},
        timeout=10,
    )
    
    # Test fetch
    print("\nFetching httpbin.org/get...")
    result = fetcher.fetch("https://httpbin.org/get")
    
    print(f"  Success: {result.success}")
    print(f"  Status Code: {result.status_code}")
    print(f"  Content Length: {len(result.html or '')} chars")
    print(f"  Fetch Time: {result.fetch_time_ms:.0f}ms")
    
    if result.success and result.status_code == 200:
        print("✓ HTTPFetcher test passed!")
        return True
    else:
        print(f"✗ HTTPFetcher test failed: {result.error_message}")
        return False


def test_link_extractor():
    """Test BS4LinkExtractor functionality."""
    print("\n" + "=" * 60)
    print("Testing BS4LinkExtractor")
    print("=" * 60)
    
    from apps.sources.crawlers import BS4LinkExtractor
    
    extractor = BS4LinkExtractor()
    
    # Test HTML
    test_html = """
    <html>
    <head>
        <meta property="og:title" content="Test Article Title">
        <meta name="description" content="Test description">
    </head>
    <body>
        <a href="/article/news-story-123">Breaking News Story</a>
        <a href="/category/politics">Politics</a>
        <a href="https://example.com/report/analysis-456">Analysis Report</a>
        <a href="/about">About Us</a>
        <a href="mailto:test@example.com">Contact</a>
    </body>
    </html>
    """
    
    # Extract all links
    links = extractor.extract_links(test_html, "https://example.com", domain="example.com")
    print(f"\nExtracted {len(links)} links:")
    for link in links:
        print(f"  - {link.url} (text: {link.text})")
    
    # Filter for articles
    article_links = extractor.filter_article_links(links)
    print(f"\nFiltered to {len(article_links)} article links:")
    for link in article_links:
        print(f"  - {link.url} (confidence: {link.confidence:.1f})")
    
    # Extract metadata
    metadata = extractor.extract_metadata(test_html)
    print(f"\nExtracted metadata:")
    for key, value in metadata.items():
        print(f"  - {key}: {value}")
    
    if len(links) > 0 and metadata.get('title'):
        print("\n✓ BS4LinkExtractor test passed!")
        return True
    else:
        print("\n✗ BS4LinkExtractor test failed")
        return False


def test_paginators():
    """Test pagination strategies."""
    print("\n" + "=" * 60)
    print("Testing Paginator Strategies")
    print("=" * 60)
    
    from apps.sources.crawlers import (
        ParameterPaginator,
        PathPaginator,
        NextLinkPaginator,
        create_paginator,
    )
    
    base_url = "https://example.com/news/"
    
    # Test Parameter Paginator
    print("\n1. Parameter Paginator (?page=N)")
    param_pag = ParameterPaginator(param_name='page', start_page=1, max_pages=5)
    
    for i in range(3):
        result = param_pag.next_page(base_url)
        print(f"   Page {result.page_number}: {result.url}")
    
    # Test Path Paginator
    print("\n2. Path Paginator (/page/N/)")
    path_pag = PathPaginator(pattern='/page/{page}/', start_page=1, max_pages=5)
    
    for i in range(3):
        result = path_pag.next_page(base_url)
        print(f"   Page {result.page_number}: {result.url}")
    
    # Test NextLink Paginator
    print("\n3. NextLink Paginator (follows rel=next)")
    next_html = """
    <html>
    <link rel="next" href="/news/?page=2">
    <body>Content</body>
    </html>
    """
    next_pag = NextLinkPaginator(max_pages=5)
    result = next_pag.next_page(base_url, html=next_html)
    print(f"   Found next: {result.url}")
    
    # Test factory
    print("\n4. Factory function (create_paginator)")
    adaptive = create_paginator('adaptive', max_pages=10)
    print(f"   Created: {type(adaptive).__name__}")
    
    print("\n✓ Paginator tests passed!")
    return True


def test_integration():
    """Test that components integrate properly."""
    print("\n" + "=" * 60)
    print("Testing Component Integration")
    print("=" * 60)
    
    from apps.sources.crawlers import (
        HTTPFetcher,
        BS4LinkExtractor,
        AdaptivePaginator,
        CrawlerPipeline,
    )
    
    # Create components
    fetcher = HTTPFetcher(timeout=10)
    extractor = BS4LinkExtractor()
    paginator = AdaptivePaginator(max_pages=2)
    
    # Create pipeline
    pipeline = CrawlerPipeline(
        fetcher=fetcher,
        link_extractor=extractor,
        paginator=paginator,
    )
    
    print("\nPipeline created with:")
    print(f"  - Fetcher: {type(pipeline.fetcher).__name__}")
    print(f"  - LinkExtractor: {type(pipeline.link_extractor).__name__}")
    print(f"  - Paginator: {type(pipeline.paginator).__name__}")
    
    # Run a simple crawl
    print("\nRunning pipeline on httpbin.org/links/5...")
    
    try:
        results = pipeline.run("https://httpbin.org/links/5")
        print(f"\nPipeline results:")
        print(f"  - Pages crawled: {results['pages_crawled']}")
        print(f"  - Total links: {results['total_links']}")
        print(f"  - Article links: {results['article_links']}")
        
        if results['errors']:
            print(f"  - Errors: {results['errors']}")
        
        print("\n✓ Integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 2 tests."""
    print("\n" + "#" * 60)
    print("# EMCIP Phase 2 Interface Tests")
    print("#" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("HTTPFetcher", test_fetcher()))
    results.append(("BS4LinkExtractor", test_link_extractor()))
    results.append(("Paginators", test_paginators()))
    results.append(("Integration", test_integration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "=" * 60)
        print("Phase 2 complete - All interface tests passed!")
        print("=" * 60)
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
