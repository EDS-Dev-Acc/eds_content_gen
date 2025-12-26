"""
Crawler package for EMCIP.
Provides various crawler implementations for different source types.

Module Structure:
- interfaces: Abstract base classes (Fetcher, LinkExtractor, Paginator)
- fetchers: HTTP fetching implementations
- extractors: Link extraction implementations  
- pagination: Pagination strategy implementations
- adapters: High-level crawler adapters using the interfaces
"""

from .base import BaseCrawler
from .scrapy_crawler import ScrapyCrawler
from .utils import (
    URLNormalizer,
    URLDeduplicator,
    DomainRateLimiter,
    normalize_url,
    fetch_urls_parallel,
    get_rate_limiter,
)

# New interface-based components
from .interfaces import (
    Fetcher,
    LinkExtractor,
    Paginator,
    FetchResult,
    ExtractedLink,
    PaginationResult,
    CrawlerPipeline,
)
from .fetchers import HTTPFetcher, HybridFetcher, PLAYWRIGHT_AVAILABLE

# Conditionally import Playwright fetchers
if PLAYWRIGHT_AVAILABLE:
    from .fetchers import PlaywrightFetcher, PlaywrightFetcherSync
else:
    PlaywrightFetcher = None
    PlaywrightFetcherSync = None

from .extractors import BS4LinkExtractor
from .extractors import (
    ContentExtractor,
    TrafilaturaExtractor,
    Newspaper3kExtractor,
    HybridContentExtractor,
    ExtractionResult,
    ExtractionQuality,
    extract_content,
    TRAFILATURA_AVAILABLE,
    NEWSPAPER_AVAILABLE,
)
from .pagination import (
    ParameterPaginator,
    PathPaginator,
    NextLinkPaginator,
    OffsetPaginator,
    AdaptivePaginator,
    create_paginator,
)
from .adapters import ModularCrawler


def get_crawler(source, use_modular: bool = False, fetcher_type: str = None, config: dict = None):
    """
    Factory function to get the appropriate crawler for a source.

    Args:
        source: Source model instance
        use_modular: If True, use the new ModularCrawler instead of ScrapyCrawler
        fetcher_type: Override fetcher type ('http', 'browser', 'hybrid')
        config: Optional config overrides to merge with source config

    Returns:
        Appropriate crawler instance
    """
    crawler_type = source.crawler_type.lower()
    
    # Determine fetcher based on source configuration
    effective_fetcher_type = fetcher_type
    if not effective_fetcher_type:
        if source.requires_javascript:
            effective_fetcher_type = 'browser'
        else:
            # Check registry for fetcher config
            from .registry import get_fetcher_config
            fetcher_config = get_fetcher_config(source.domain)
            effective_fetcher_type = fetcher_config.get('fetcher_type', 'http')

    # Allow explicit modular crawler request
    if use_modular or crawler_type == 'modular':
        fetcher = _create_fetcher(effective_fetcher_type, source)
        return ModularCrawler(source, fetcher=fetcher, config=config)
    
    if crawler_type == 'scrapy':
        return ScrapyCrawler(source, config=config)
    elif crawler_type == 'playwright':
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )
        fetcher = _create_fetcher('browser', source)
        return ModularCrawler(source, fetcher=fetcher, config=config)
    elif crawler_type == 'hybrid':
        fetcher = _create_fetcher('hybrid', source)
        return ModularCrawler(source, fetcher=fetcher, config=config)
    elif crawler_type == 'selenium':
        raise NotImplementedError("Selenium crawler not yet implemented")
    else:
        # Default to Scrapy
        return ScrapyCrawler(source, config=config)


def _create_fetcher(fetcher_type: str, source) -> Fetcher:
    """
    Create a fetcher based on type.
    
    Args:
        fetcher_type: 'http', 'browser', or 'hybrid'
        source: Source model instance
        
    Returns:
        Fetcher instance
    """
    from .registry import get_combined_config
    config = get_combined_config(source)
    
    # Build headers
    headers = {
        'User-Agent': config.get('user_agent', 'EMCIP-Bot/1.0'),
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    if source.custom_headers:
        headers.update(source.custom_headers)
    
    delay = config.get('delay', 2.0)
    timeout = config.get('timeout', 30)
    
    if fetcher_type == 'browser':
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not available")
        return PlaywrightFetcherSync(
            timeout=timeout,
            default_delay=delay,
            headers=headers,
        )
    elif fetcher_type == 'hybrid':
        return HybridFetcher(
            default_delay=delay,
            headers=headers,
            force_browser_domains=config.get('force_browser_domains', []),
        )
    else:
        return HTTPFetcher(
            timeout=timeout,
            default_delay=delay,
            headers=headers,
        )


__all__ = [
    # Existing crawlers
    'BaseCrawler',
    'ScrapyCrawler',
    'ModularCrawler',
    'get_crawler',
    '_create_fetcher',
    
    # URL utilities
    'URLNormalizer',
    'URLDeduplicator', 
    'DomainRateLimiter',
    'normalize_url',
    'fetch_urls_parallel',
    'get_rate_limiter',
    
    # Interfaces (ABCs)
    'Fetcher',
    'LinkExtractor',
    'Paginator',
    'FetchResult',
    'ExtractedLink',
    'PaginationResult',
    'CrawlerPipeline',
    
    # Fetcher implementations
    'HTTPFetcher',
    'HybridFetcher',
    'PlaywrightFetcher',
    'PlaywrightFetcherSync',
    'PLAYWRIGHT_AVAILABLE',
    
    # LinkExtractor implementations
    'BS4LinkExtractor',
    
    # Content extractor implementations
    'ContentExtractor',
    'TrafilaturaExtractor',
    'Newspaper3kExtractor',
    'HybridContentExtractor',
    'ExtractionResult',
    'ExtractionQuality',
    'extract_content',
    'TRAFILATURA_AVAILABLE',
    'NEWSPAPER_AVAILABLE',
    
    # Paginator implementations
    'ParameterPaginator',
    'PathPaginator',
    'NextLinkPaginator',
    'OffsetPaginator',
    'AdaptivePaginator',
    'create_paginator',
]
