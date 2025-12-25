"""
Playwright-based fetcher for JavaScript-rendered pages.

Uses headless Chromium to fully render pages that require JavaScript.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

from ..interfaces import Fetcher, FetcherType, FetchResult
from ..utils import DomainRateLimiter

logger = logging.getLogger(__name__)

# Check if playwright is available
try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Install with: pip install playwright && playwright install chromium")


class PlaywrightFetcher(Fetcher):
    """
    Browser-based fetcher using Playwright.
    
    Features:
    - Full JavaScript rendering
    - Wait for network idle
    - Screenshot capability (for debugging)
    - Cookie/session persistence
    - Stealth mode options
    """
    
    DEFAULT_TIMEOUT = 30000  # 30 seconds in ms
    DEFAULT_WAIT_UNTIL = 'networkidle'  # 'load', 'domcontentloaded', 'networkidle'
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30,
        wait_until: str = 'networkidle',
        rate_limiter: Optional[DomainRateLimiter] = None,
        default_delay: float = 3.0,
        user_agent: Optional[str] = None,
        viewport: Optional[Dict[str, int]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize PlaywrightFetcher.
        
        Args:
            headless: Run browser in headless mode
            timeout: Page load timeout in seconds
            wait_until: When to consider page loaded ('load', 'domcontentloaded', 'networkidle')
            rate_limiter: Optional rate limiter for requests
            default_delay: Default delay between requests (seconds)
            user_agent: Custom user agent string
            viewport: Browser viewport size {'width': 1920, 'height': 1080}
            headers: Custom headers to set
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )
        
        self.headless = headless
        self.timeout = timeout * 1000  # Convert to ms
        self.wait_until = wait_until
        self.rate_limiter = rate_limiter or DomainRateLimiter(default_delay=default_delay)
        self.user_agent = user_agent
        self.viewport = viewport or {'width': 1920, 'height': 1080}
        self.custom_headers = headers or {}
        
        # Browser instance (lazy loaded)
        self._browser: Optional[Browser] = None
        self._playwright = None
    
    @property
    def fetcher_type(self) -> FetcherType:
        return FetcherType.BROWSER
    
    async def _ensure_browser(self):
        """Ensure browser is started."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
            )
            logger.info("Playwright browser started")
    
    async def _create_context(self):
        """Create a new browser context with settings."""
        await self._ensure_browser()
        
        context_options = {
            'viewport': self.viewport,
            'ignore_https_errors': True,
        }
        
        if self.user_agent:
            context_options['user_agent'] = self.user_agent
        
        if self.custom_headers:
            context_options['extra_http_headers'] = self.custom_headers
        
        return await self._browser.new_context(**context_options)
    
    async def _fetch_async(self, url: str, headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """Async implementation of fetch."""
        start_time = time.time()
        
        # Apply rate limiting
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        self.rate_limiter.wait_if_needed(domain)
        
        context = None
        page = None
        
        try:
            context = await self._create_context()
            page = await context.new_page()
            
            # Set additional headers if provided
            if headers:
                await page.set_extra_http_headers(headers)
            
            # Navigate to page
            response = await page.goto(
                url,
                timeout=self.timeout,
                wait_until=self.wait_until,
            )
            
            # Wait for any dynamic content
            await page.wait_for_load_state('networkidle', timeout=self.timeout)
            
            # Get rendered HTML
            html = await page.content()
            
            fetch_time_ms = int((time.time() - start_time) * 1000)
            
            # Record request
            self.rate_limiter.record_request(domain)
            
            status_code = response.status if response else 200
            final_url = page.url
            
            return FetchResult(
                url=url,
                html=html,
                status_code=status_code,
                final_url=final_url,
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=fetch_time_ms,
            )
            
        except PlaywrightTimeout:
            return FetchResult(
                url=url,
                error="Page load timed out",
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(f"Playwright error fetching {url}: {e}")
            return FetchResult(
                url=url,
                error=str(e),
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=int((time.time() - start_time) * 1000),
            )
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
    
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """
        Fetch a URL with full JavaScript rendering.
        
        Args:
            url: URL to fetch
            headers: Optional custom headers
            
        Returns:
            FetchResult with rendered HTML
        """
        # Run async code in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._fetch_async(url, headers))
    
    async def _fetch_many_async(
        self, 
        urls: List[str], 
        headers: Optional[Dict[str, str]] = None,
        max_concurrent: int = 3,
    ) -> List[FetchResult]:
        """Async implementation of fetch_many."""
        # For browser-based fetching, we limit concurrency more strictly
        # to avoid overwhelming resources
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(url: str) -> FetchResult:
            async with semaphore:
                return await self._fetch_async(url, headers)
        
        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)
    
    def fetch_many(
        self, 
        urls: List[str], 
        headers: Optional[Dict[str, str]] = None,
        max_concurrent: int = 3,
    ) -> List[FetchResult]:
        """
        Fetch multiple URLs with JavaScript rendering.
        
        Note: Browser-based fetching is more resource-intensive,
        so max_concurrent is typically lower than HTTP fetching.
        
        Args:
            urls: List of URLs to fetch
            headers: Optional custom headers
            max_concurrent: Max concurrent browser contexts (default: 3)
            
        Returns:
            List of FetchResults
        """
        if not urls:
            return []
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self._fetch_many_async(urls, headers, max_concurrent)
        )
    
    async def _close_async(self):
        """Async cleanup."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    def close(self):
        """Clean up browser resources."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self._close_async())
        logger.info("Playwright browser closed")


class PlaywrightFetcherSync:
    """
    Synchronous wrapper for PlaywrightFetcher.
    
    Uses sync_playwright for simpler integration.
    """
    
    def __init__(self, **kwargs):
        """Initialize with same args as PlaywrightFetcher."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )
        
        self.headless = kwargs.get('headless', True)
        self.timeout = kwargs.get('timeout', 30) * 1000
        self.wait_until = kwargs.get('wait_until', 'networkidle')
        self.rate_limiter = kwargs.get('rate_limiter') or DomainRateLimiter(
            default_delay=kwargs.get('default_delay', 3.0)
        )
        self.user_agent = kwargs.get('user_agent')
        self.viewport = kwargs.get('viewport', {'width': 1920, 'height': 1080})
        self.custom_headers = kwargs.get('headers', {})
        
        # Sync playwright
        from playwright.sync_api import sync_playwright
        self._sync_playwright = sync_playwright
        self._playwright = None
        self._browser = None
    
    @property
    def fetcher_type(self) -> FetcherType:
        return FetcherType.BROWSER
    
    def _ensure_browser(self):
        """Ensure browser is started."""
        if self._browser is None:
            self._playwright = self._sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            logger.info("Playwright browser started (sync)")
    
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """Fetch a URL with full JavaScript rendering."""
        start_time = time.time()
        
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        self.rate_limiter.wait_if_needed(domain)
        
        self._ensure_browser()
        
        context = None
        page = None
        
        try:
            context_options = {
                'viewport': self.viewport,
                'ignore_https_errors': True,
            }
            if self.user_agent:
                context_options['user_agent'] = self.user_agent
            if self.custom_headers:
                context_options['extra_http_headers'] = self.custom_headers
            
            context = self._browser.new_context(**context_options)
            page = context.new_page()
            
            if headers:
                page.set_extra_http_headers(headers)
            
            response = page.goto(url, timeout=self.timeout, wait_until=self.wait_until)
            page.wait_for_load_state('networkidle', timeout=self.timeout)
            
            html = page.content()
            fetch_time_ms = int((time.time() - start_time) * 1000)
            
            self.rate_limiter.record_request(domain)
            
            return FetchResult(
                url=url,
                html=html,
                status_code=response.status if response else 200,
                final_url=page.url,
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=fetch_time_ms,
            )
            
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            return FetchResult(
                url=url,
                error=str(e),
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=int((time.time() - start_time) * 1000),
            )
        finally:
            if page:
                page.close()
            if context:
                context.close()
    
    def fetch_many(
        self, 
        urls: List[str], 
        headers: Optional[Dict[str, str]] = None,
        max_concurrent: int = 1,
    ) -> List[FetchResult]:
        """Fetch multiple URLs sequentially (sync version)."""
        return [self.fetch(url, headers) for url in urls]
    
    def close(self):
        """Clean up browser resources."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.info("Playwright browser closed (sync)")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
