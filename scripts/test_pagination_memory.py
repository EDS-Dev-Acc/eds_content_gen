#!/usr/bin/env python
"""
Test script for Phase 3: Pagination Memory.

Verifies that:
1. Source model has pagination_state field
2. Pagination strategies are persisted after successful crawls
3. Previously successful strategies are preferred on subsequent crawls
4. Combined config merges registry + source + learned state
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from django.utils import timezone


def test_source_pagination_state():
    """Test that Source model has pagination state management."""
    print("=" * 60)
    print("Testing Source Pagination State")
    print("=" * 60)
    
    from apps.sources.models import Source
    
    # Create or get a test source
    source, created = Source.objects.get_or_create(
        domain='pagination-test.example.com',
        defaults={
            'name': 'Pagination Test Source',
            'url': 'https://pagination-test.example.com/news/',
            'status': 'active',
        }
    )
    
    print(f"\nTest source: {source.name}")
    print(f"  Initial pagination_state: {source.pagination_state}")
    
    # Test recording pagination success
    source.record_pagination_success(
        strategy_type='parameter',
        pages_crawled=5,
        detected_params={'param_name': 'page', 'start_page': 1}
    )
    
    # Refresh from database
    source.refresh_from_db()
    
    print(f"  After recording success: {source.pagination_state}")
    
    # Check stored values
    assert source.pagination_state.get('strategy_type') == 'parameter'
    assert source.pagination_state.get('pages_crawled') == 5
    assert source.pagination_state.get('success_count') >= 1
    assert 'last_success_at' in source.pagination_state
    
    # Test get_pagination_strategy
    strategy = source.get_pagination_strategy()
    print(f"  get_pagination_strategy(): {strategy}")
    assert strategy == 'parameter'
    
    # Test get_preferred_paginator_config
    config = source.get_preferred_paginator_config()
    print(f"  get_preferred_paginator_config(): {config}")
    assert config['strategy'] == 'parameter'
    assert config['param_name'] == 'page'
    
    # Record another success to test increment
    source.record_pagination_success(
        strategy_type='parameter',
        pages_crawled=8,
        detected_params={'param_name': 'page', 'start_page': 1}
    )
    source.refresh_from_db()
    
    print(f"  After 2nd success, count: {source.pagination_state.get('success_count')}")
    assert source.pagination_state.get('success_count') >= 2
    assert source.pagination_state.get('pages_crawled') == 8  # Most recent
    
    # Clean up
    source.delete()
    
    print("\n[PASS] Source pagination state test passed!")
    return True


def test_registry_combined_config():
    """Test combined configuration from multiple sources."""
    print("\n" + "=" * 60)
    print("Testing Combined Configuration")
    print("=" * 60)
    
    from apps.sources.models import Source
    from apps.sources.crawlers.registry import get_combined_config, register_site
    
    # Create a test source
    source, _ = Source.objects.get_or_create(
        domain='combined-test.example.com',
        defaults={
            'name': 'Combined Config Test',
            'url': 'https://combined-test.example.com/articles/',
            'status': 'active',
            'requires_javascript': True,
            'crawler_config': {
                'delay': 3.0,
                'max_pages': 15,
            },
        }
    )
    
    print(f"\nTest source: {source.name}")
    
    # Register in registry
    register_site('combined-test.example.com', {
        'include_patterns': ['/articles/'],
        'pagination_type': 'path',
        'page_path_format': '/page/{page}/',
    })
    
    # Get combined config (no learned state yet)
    config = get_combined_config(source)
    print(f"\nCombined config (before learning):")
    print(f"  pagination_type: {config['pagination_type']}")
    print(f"  page_path_format: {config['page_path_format']}")
    print(f"  requires_javascript: {config['requires_javascript']}")
    print(f"  delay: {config['delay']}")
    print(f"  max_pages: {config['max_pages']}")
    print(f"  include_patterns: {config['include_patterns']}")
    
    assert config['pagination_type'] == 'path'
    assert config['delay'] == 3.0  # From crawler_config
    assert config['requires_javascript'] == True  # From model
    assert config['include_patterns'] == ['/articles/']  # From registry
    
    # Now simulate learning a different strategy
    source.record_pagination_success(
        strategy_type='next_link',
        pages_crawled=7,
        detected_params={}
    )
    source.refresh_from_db()
    
    # Get combined config again - learned state should override
    config = get_combined_config(source)
    print(f"\nCombined config (after learning next_link):")
    print(f"  pagination_type: {config['pagination_type']}")
    
    assert config['pagination_type'] == 'next_link'  # Learned overrides registry
    
    # Clean up
    source.delete()
    
    print("\n[PASS] Combined configuration test passed!")
    return True


def test_paginator_state_persistence():
    """Test that paginator state is correctly formatted for persistence."""
    print("\n" + "=" * 60)
    print("Testing Paginator State Persistence")
    print("=" * 60)
    
    from apps.sources.crawlers.pagination import (
        ParameterPaginator,
        PathPaginator,
        NextLinkPaginator,
        AdaptivePaginator,
    )
    
    # Test ParameterPaginator state
    param_pag = ParameterPaginator(param_name='p', start_page=0, max_pages=20)
    param_pag.next_page("https://example.com/news/")
    state = param_pag.get_state()
    print(f"\nParameterPaginator state: {state}")
    assert state['type'] == 'parameter'
    assert state['param_name'] == 'p'
    assert state['current_page'] == 1
    
    # Test PathPaginator state
    path_pag = PathPaginator(pattern='/page/{page}/', start_page=1, max_pages=10)
    path_pag.next_page("https://example.com/blog/")
    state = path_pag.get_state()
    print(f"PathPaginator state: {state}")
    assert state['type'] == 'path'
    assert state['pattern'] == '/page/{page}/'
    
    # Test NextLinkPaginator state
    next_pag = NextLinkPaginator(max_pages=5)
    state = next_pag.get_state()
    print(f"NextLinkPaginator state: {state}")
    assert state['type'] == 'next_link'
    
    # Test AdaptivePaginator state (before detection)
    adaptive = AdaptivePaginator(max_pages=10)
    state = adaptive.get_state()
    print(f"AdaptivePaginator state (before): {state}")
    assert state['type'] == 'adaptive'
    assert state['detected_strategy'] == {}
    
    # Trigger detection
    html_with_page = """
    <html>
    <body>
        <a href="/news/?page=2">Next</a>
    </body>
    </html>
    """
    adaptive.next_page("https://example.com/news/?page=1", html=html_with_page)
    state = adaptive.get_state()
    print(f"AdaptivePaginator state (after): {state}")
    assert state['detected_strategy'] != {}
    
    print("\n[PASS] Paginator state persistence test passed!")
    return True


def test_modular_crawler_uses_learned_strategy():
    """Test that ModularCrawler uses previously learned pagination strategy."""
    print("\n" + "=" * 60)
    print("Testing ModularCrawler Learned Strategy")
    print("=" * 60)
    
    from apps.sources.models import Source
    from apps.sources.crawlers.adapters import ModularCrawler
    
    # Create a source with learned pagination
    source, _ = Source.objects.get_or_create(
        domain='modular-test.example.com',
        defaults={
            'name': 'Modular Crawler Test',
            'url': 'https://modular-test.example.com/articles/',
            'status': 'active',
        }
    )
    
    # Pre-set pagination state (simulating previous successful crawl)
    source.pagination_state = {
        'strategy_type': 'path',
        'last_success_at': timezone.now().isoformat(),
        'pages_crawled': 5,
        'detected_params': {
            'pattern': '/archive/{page}/',
            'start_page': 0,
        },
        'success_count': 3,
    }
    source.save()
    source.refresh_from_db()
    
    print(f"\nSource: {source.name}")
    print(f"  Pre-set pagination_state: {source.pagination_state}")
    
    # Create crawler
    crawler = ModularCrawler(source)
    
    # Check that it's using PathPaginator with the learned settings
    paginator = crawler.paginator
    state = paginator.get_state()
    print(f"\nCrawler's paginator state: {state}")
    
    # Should be using path strategy
    assert state['type'] == 'path'
    
    # Clean up
    source.delete()
    
    print("\n[PASS] ModularCrawler learned strategy test passed!")
    return True


def main():
    """Run all Phase 3 tests."""
    print("\n" + "#" * 60)
    print("# EMCIP Phase 3 - Pagination Memory Tests")
    print("#" * 60)
    
    results = []
    
    results.append(("Source Pagination State", test_source_pagination_state()))
    results.append(("Combined Configuration", test_registry_combined_config()))
    results.append(("Paginator State Persistence", test_paginator_state_persistence()))
    results.append(("ModularCrawler Learned Strategy", test_modular_crawler_uses_learned_strategy()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "[PASS]" if passed_test else "[FAIL]"
        print(f"  {status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "=" * 60)
        print("Phase 3 complete - Pagination memory working!")
        print("=" * 60)
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
