"""
HTTP Fetcher implementation using requests library.

This is the default fetcher for non-JavaScript sites.
"""

import logging
import time
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..interfaces import Fetcher, FetcherType, FetchResult
from ..utils import DomainRateLimiter, fetch_urls_parallel

logger = logging.getLogger(__name__)


class HTTPFetcher(Fetcher):
    """
    HTTP-based fetcher using the requests library.
    
    Features:
    - Configurable timeouts and retries
    - Per-domain rate limiting
    - Parallel fetching via aiohttp
    - Custom headers support
    """
    
    DEFAULT_USER_AGENT = 'EMCIP-Bot/1.0 (Content Intelligence Platform)'
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 2
    
    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate_limiter: Optional[DomainRateLimiter] = None,
        default_delay: float = 2.0,
        headers: Optional[Dict[str, str]] = None,
        rate_limit_delay: Optional[float] = None,  # Alias for default_delay
    ):
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Handle alias for delay
        delay = rate_limit_delay if rate_limit_delay is not None else default_delay
        self.rate_limiter = rate_limiter or DomainRateLimiter(default_delay=delay)
        
        # Store custom headers for all requests
        self.custom_headers = headers or {}
        
        # Configure session with retries
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @property
    def fetcher_type(self) -> FetcherType:
        return FetcherType.HTTP
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default request headers including custom headers."""
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        # Apply custom headers set at init
        if self.custom_headers:
            headers.update(self.custom_headers)
        return headers
    
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """
        Fetch content from a URL.
        
        Args:
            url: The URL to fetch
            headers: Optional custom headers
            
        Returns:
            FetchResult with content or error
        """
        start_time = time.time()
        
        # SSRF validation before any network request
        try:
            from apps.core.security import validate_url_ssrf
            is_safe, message = validate_url_ssrf(url)
            if not is_safe:
                logger.warning(f"SSRF blocked for {url}: {message}")
                return FetchResult(
                    url=url,
                    error=f"Security: {message}",
                    fetcher_type=self.fetcher_type.value,
                    fetch_time_ms=0,
                )
        except ImportError:
            pass  # Security module not available, proceed without check
        
        # Apply rate limiting
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        self.rate_limiter.wait_if_needed(domain)
        
        # Merge headers
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
        
        try:
            response = self.session.get(
                url,
                headers=request_headers,
                timeout=self.timeout,
                allow_redirects=True,
            )
            
            fetch_time_ms = int((time.time() - start_time) * 1000)
            
            # Record request for rate limiting
            self.rate_limiter.record_request(domain)
            
            if response.status_code != 200:
                return FetchResult(
                    url=url,
                    status_code=response.status_code,
                    final_url=response.url,
                    error=f"HTTP {response.status_code}",
                    fetcher_type=self.fetcher_type.value,
                    fetch_time_ms=fetch_time_ms,
                )
            
            return FetchResult(
                url=url,
                html=response.text,
                status_code=response.status_code,
                final_url=response.url,
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=fetch_time_ms,
                headers=dict(response.headers),
            )
            
        except requests.Timeout:
            return FetchResult(
                url=url,
                error="Request timed out",
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=int((time.time() - start_time) * 1000),
            )
        except requests.RequestException as e:
            return FetchResult(
                url=url,
                error=str(e),
                fetcher_type=self.fetcher_type.value,
                fetch_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def fetch_many(
        self, 
        urls: List[str], 
        headers: Optional[Dict[str, str]] = None,
        max_concurrent: int = 5
    ) -> List[FetchResult]:
        """
        Fetch multiple URLs using async parallel fetching.
        
        Falls back to sequential fetching if aiohttp is unavailable.
        """
        if not urls:
            return []
        
        # Merge headers
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
        
        # Try parallel fetch
        try:
            results = fetch_urls_parallel(
                urls,
                headers=request_headers,
                max_concurrent=max_concurrent,
                timeout=self.timeout,
                rate_limiter=self.rate_limiter,
            )
            
            # Convert to FetchResult objects
            fetch_results = []
            for url, html, status_code, error in results:
                fetch_results.append(FetchResult(
                    url=url,
                    html=html if not error else None,
                    status_code=status_code,
                    error=error,
                    fetcher_type=self.fetcher_type.value,
                ))
            
            return fetch_results
            
        except Exception as e:
            logger.warning(f"Parallel fetch failed, falling back to sequential: {e}")
            return [self.fetch(url, headers) for url in urls]
    
    def close(self) -> None:
        """Close the session."""
        if self.session:
            self.session.close()
