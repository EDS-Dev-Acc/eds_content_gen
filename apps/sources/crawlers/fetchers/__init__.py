"""
Fetcher package for EMCIP crawlers.

Provides different fetching strategies:
- HTTPFetcher: Fast HTTP-based fetching for static pages
- PlaywrightFetcher: Browser-based fetching for JS-heavy pages
- HybridFetcher: Smart HTTP-first with browser fallback
"""

from .http_fetcher import HTTPFetcher
from .hybrid_fetcher import HybridFetcher

# Playwright fetcher is optional (requires playwright package)
try:
    from .playwright_fetcher import (
        PlaywrightFetcher, 
        PlaywrightFetcherSync,
        PLAYWRIGHT_AVAILABLE,
    )
except ImportError:
    PlaywrightFetcher = None
    PlaywrightFetcherSync = None
    PLAYWRIGHT_AVAILABLE = False

__all__ = [
    'HTTPFetcher',
    'HybridFetcher',
    'PlaywrightFetcher',
    'PlaywrightFetcherSync',
    'PLAYWRIGHT_AVAILABLE',
]
