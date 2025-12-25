"""
Hybrid fetcher that tries HTTP first, falls back to Playwright for JS-heavy pages.

This provides the best of both worlds:
- Fast HTTP fetching for static pages
- Full JS rendering when needed
"""

import logging
from typing import Dict, List, Optional

from ..interfaces import Fetcher, FetcherType, FetchResult
from ..utils import DomainRateLimiter
from .http_fetcher import HTTPFetcher

logger = logging.getLogger(__name__)

# Check if playwright is available
try:
    from .playwright_fetcher import PlaywrightFetcherSync, PLAYWRIGHT_AVAILABLE
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class HybridFetcher(Fetcher):
    """
    Smart fetcher that uses HTTP first and falls back to browser rendering.
    
    Decision logic:
    1. Try HTTP fetch first (fast)
    2. Check if page looks incomplete (signs of JS-required content)
    3. If incomplete, retry with Playwright
    4. Remember which domains need browser rendering
    
    Features:
    - Automatic JS detection
    - Domain-level caching of fetcher preference
    - Configurable detection heuristics
    """
    
    # Signs that a page requires JavaScript
    JS_REQUIRED_INDICATORS = [
        'enable JavaScript',
        'JavaScript is required',
        'please enable JavaScript',
        'requires JavaScript',
        'noscript',
        '__NEXT_DATA__',  # Next.js
        'window.__INITIAL_STATE__',  # Redux SSR
        '<div id="root"></div>',  # Empty React root
        '<div id="app"></div>',  # Empty Vue root
        'Loading...',
        'Please wait...',
    ]
    
    # Minimum content length to consider page valid
    MIN_CONTENT_LENGTH = 1000
    
    def __init__(
        self,
        http_fetcher: Optional[HTTPFetcher] = None,
        playwright_fetcher: Optional[Fetcher] = None,
        rate_limiter: Optional[DomainRateLimiter] = None,
        default_delay: float = 2.0,
        force_browser_domains: Optional[List[str]] = None,
        js_indicators: Optional[List[str]] = None,
        min_content_length: int = 1000,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize HybridFetcher.
        
        Args:
            http_fetcher: HTTP fetcher instance (created if not provided)
            playwright_fetcher: Playwright fetcher (created lazily if needed)
            rate_limiter: Shared rate limiter
            default_delay: Default delay between requests
            force_browser_domains: Domains that always use browser
            js_indicators: Custom JS-required indicators
            min_content_length: Minimum valid content length
            headers: Custom headers
        """
        self.rate_limiter = rate_limiter or DomainRateLimiter(default_delay=default_delay)
        self.force_browser_domains = set(d.lower() for d in (force_browser_domains or []))
        self.js_indicators = js_indicators or self.JS_REQUIRED_INDICATORS
        self.min_content_length = min_content_length
        self.custom_headers = headers or {}
        
        # Initialize HTTP fetcher
        self.http_fetcher = http_fetcher or HTTPFetcher(
            rate_limiter=self.rate_limiter,
            headers=headers,
        )
        
        # Playwright fetcher (lazy loaded)
        self._playwright_fetcher = playwright_fetcher
        
        # Track which domains needed browser
        self._browser_domains: set = set()
    
    @property
    def fetcher_type(self) -> FetcherType:
        return FetcherType.HYBRID
    
    def _get_playwright_fetcher(self) -> Optional[Fetcher]:
        """Lazily create Playwright fetcher."""
        if self._playwright_fetcher is None and PLAYWRIGHT_AVAILABLE:
            try:
                self._playwright_fetcher = PlaywrightFetcherSync(
                    rate_limiter=self.rate_limiter,
                    headers=self.custom_headers,
                )
            except Exception as e:
                logger.warning(f"Failed to create Playwright fetcher: {e}")
        return self._playwright_fetcher
    
    def _needs_browser(self, domain: str) -> bool:
        """Check if domain is known to need browser rendering."""
        return domain.lower() in self._browser_domains or domain.lower() in self.force_browser_domains
    
    def _looks_like_js_page(self, html: str) -> bool:
        """
        Check if HTML looks like it requires JavaScript.
        
        Args:
            html: Page HTML content
            
        Returns:
            True if page likely needs JS rendering
        """
        if not html:
            return True
        
        # Too short - likely JS-rendered
        if len(html) < self.min_content_length:
            return True
        
        html_lower = html.lower()
        
        # Check for JS-required indicators
        for indicator in self.js_indicators:
            if indicator.lower() in html_lower:
                return True
        
        return False
    
    def _record_browser_needed(self, domain: str):
        """Record that a domain needs browser rendering."""
        self._browser_domains.add(domain.lower())
        logger.info(f"Domain {domain} marked as requiring browser rendering")
    
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """
        Fetch URL with automatic HTTP/browser selection.
        
        Args:
            url: URL to fetch
            headers: Optional custom headers
            
        Returns:
            FetchResult with content
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        # Check if we know this domain needs browser
        if self._needs_browser(domain):
            fetcher = self._get_playwright_fetcher()
            if fetcher:
                logger.debug(f"Using browser for known JS domain: {domain}")
                return fetcher.fetch(url, headers)
            else:
                logger.warning(f"Playwright unavailable, falling back to HTTP for {domain}")
        
        # Try HTTP first
        result = self.http_fetcher.fetch(url, headers)
        
        # Check if successful
        if not result.success:
            return result
        
        # Check if page looks like it needs JS
        if self._looks_like_js_page(result.html):
            logger.info(f"Page {url} appears to need JavaScript, retrying with browser")
            
            fetcher = self._get_playwright_fetcher()
            if fetcher:
                self._record_browser_needed(domain)
                browser_result = fetcher.fetch(url, headers)
                
                # Return browser result if successful, otherwise original
                if browser_result.success:
                    return browser_result
                else:
                    logger.warning(f"Browser fetch failed, using HTTP result: {browser_result.error}")
        
        return result
    
    def fetch_many(
        self, 
        urls: List[str], 
        headers: Optional[Dict[str, str]] = None,
        max_concurrent: int = 5,
    ) -> List[FetchResult]:
        """
        Fetch multiple URLs with hybrid strategy.
        
        URLs are grouped by whether they need browser rendering,
        then fetched with appropriate fetcher.
        """
        if not urls:
            return []
        
        from urllib.parse import urlparse
        
        # Separate URLs by fetcher type
        http_urls = []
        browser_urls = []
        url_order = {url: i for i, url in enumerate(urls)}
        
        for url in urls:
            domain = urlparse(url).netloc
            if self._needs_browser(domain):
                browser_urls.append(url)
            else:
                http_urls.append(url)
        
        results = [None] * len(urls)
        
        # Fetch HTTP URLs
        if http_urls:
            http_results = self.http_fetcher.fetch_many(http_urls, headers, max_concurrent)
            
            # Check results and maybe retry with browser
            for i, result in enumerate(http_results):
                url = http_urls[i]
                
                if result.success and self._looks_like_js_page(result.html):
                    # Needs browser - add to browser queue
                    domain = urlparse(url).netloc
                    self._record_browser_needed(domain)
                    browser_urls.append(url)
                else:
                    results[url_order[url]] = result
        
        # Fetch browser URLs
        if browser_urls:
            fetcher = self._get_playwright_fetcher()
            if fetcher:
                # Browser fetching is slower, use lower concurrency
                browser_results = fetcher.fetch_many(
                    browser_urls, 
                    headers, 
                    max_concurrent=min(3, max_concurrent)
                )
                for i, result in enumerate(browser_results):
                    url = browser_urls[i]
                    results[url_order[url]] = result
            else:
                # No playwright - use HTTP results or error
                for url in browser_urls:
                    if results[url_order[url]] is None:
                        results[url_order[url]] = FetchResult(
                            url=url,
                            error="Playwright unavailable for JS-required page",
                            fetcher_type=self.fetcher_type.value,
                        )
        
        return results
    
    def get_browser_domains(self) -> List[str]:
        """Get list of domains that needed browser rendering."""
        return list(self._browser_domains)
    
    def close(self):
        """Clean up resources."""
        if self._playwright_fetcher:
            self._playwright_fetcher.close()
            self._playwright_fetcher = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
