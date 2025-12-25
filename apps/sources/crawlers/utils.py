"""
Utility functions for crawlers.
Provides URL normalization, rate limiting, and async fetching helpers.
"""

import asyncio
import logging
import re
import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, unquote

logger = logging.getLogger(__name__)


# =============================================================================
# URL Normalization
# =============================================================================

class URLNormalizer:
    """
    Normalize URLs to canonical form for better duplicate detection.
    
    Handles:
    - Lowercasing scheme and host
    - Removing default ports (80 for http, 443 for https)
    - Removing trailing slashes (configurable)
    - Sorting query parameters
    - Removing tracking parameters (utm_*, fbclid, etc.)
    - Removing fragments
    - Decoding percent-encoded characters
    """
    
    # Common tracking parameters to strip
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'utm_id', 'utm_source_platform', 'utm_creative_format',
        'fbclid', 'gclid', 'gclsrc', 'dclid',
        'msclkid', 'mc_eid', 'mc_cid',
        'ref', 'source', 'campaign',
        '_ga', '_gl', '_hsenc', '_hsmi',
        'mkt_tok', 'trk', 'trkInfo',
    }
    
    # Default ports to remove
    DEFAULT_PORTS = {
        'http': 80,
        'https': 443,
    }
    
    def __init__(
        self,
        remove_trailing_slash: bool = True,
        remove_fragments: bool = True,
        remove_tracking_params: bool = True,
        sort_query_params: bool = True,
        lowercase_path: bool = False,
        extra_tracking_params: Optional[set] = None,
    ):
        self.remove_trailing_slash = remove_trailing_slash
        self.remove_fragments = remove_fragments
        self.remove_tracking_params = remove_tracking_params
        self.sort_query_params = sort_query_params
        self.lowercase_path = lowercase_path
        
        self.tracking_params = self.TRACKING_PARAMS.copy()
        if extra_tracking_params:
            self.tracking_params.update(extra_tracking_params)
    
    def normalize(self, url: str) -> str:
        """
        Normalize a URL to its canonical form.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL string
        """
        if not url:
            return url
        
        try:
            # Parse the URL
            parsed = urlparse(url)
            
            # Lowercase scheme and host
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # Remove default ports
            if ':' in netloc:
                host, port_str = netloc.rsplit(':', 1)
                try:
                    port = int(port_str)
                    if self.DEFAULT_PORTS.get(scheme) == port:
                        netloc = host
                except ValueError:
                    pass
            
            # Process path
            path = unquote(parsed.path)  # Decode percent-encoded chars
            if self.lowercase_path:
                path = path.lower()
            
            # Remove trailing slash (but keep root /)
            if self.remove_trailing_slash and path != '/' and path.endswith('/'):
                path = path.rstrip('/')
            
            # Normalize empty path to /
            if not path:
                path = '/'
            
            # Process query parameters
            query = self._normalize_query(parsed.query)
            
            # Handle fragments
            fragment = '' if self.remove_fragments else parsed.fragment
            
            # Rebuild URL
            normalized = urlunparse((
                scheme,
                netloc,
                path,
                parsed.params,
                query,
                fragment
            ))
            
            return normalized
            
        except Exception as e:
            logger.warning(f"Error normalizing URL {url}: {e}")
            return url
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query string."""
        if not query:
            return ''
        
        try:
            params = parse_qs(query, keep_blank_values=True)
            
            # Remove tracking parameters
            if self.remove_tracking_params:
                params = {
                    k: v for k, v in params.items()
                    if k.lower() not in self.tracking_params
                }
            
            if not params:
                return ''
            
            # Sort parameters if requested
            if self.sort_query_params:
                params = dict(sorted(params.items()))
            
            return urlencode(params, doseq=True)
            
        except Exception:
            return query
    
    def are_same_url(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs point to the same resource.
        
        Args:
            url1: First URL
            url2: Second URL
            
        Returns:
            True if URLs are equivalent after normalization
        """
        return self.normalize(url1) == self.normalize(url2)


# Default normalizer instance
default_normalizer = URLNormalizer()


def normalize_url(url: str) -> str:
    """Convenience function to normalize a URL using default settings."""
    return default_normalizer.normalize(url)


# =============================================================================
# Per-Domain Rate Limiting
# =============================================================================

class DomainRateLimiter:
    """
    Thread-safe per-domain rate limiter.
    
    Tracks the last request time for each domain and enforces
    minimum delays between requests to the same domain.
    """
    
    def __init__(self, default_delay: float = 2.0, domain_delays: Optional[Dict[str, float]] = None):
        """
        Initialize the rate limiter.
        
        Args:
            default_delay: Default delay in seconds between requests to same domain
            domain_delays: Optional dict of domain -> delay overrides
        """
        self.default_delay = default_delay
        self.domain_delays = domain_delays or {}
        self._last_request_times: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def get_delay_for_domain(self, domain: str) -> float:
        """Get the configured delay for a domain."""
        return self.domain_delays.get(domain.lower(), self.default_delay)
    
    def set_delay_for_domain(self, domain: str, delay: float) -> None:
        """Set a custom delay for a specific domain."""
        self.domain_delays[domain.lower()] = delay
    
    def wait_if_needed(self, domain: str) -> float:
        """
        Wait if necessary to respect rate limits for the domain.
        
        Args:
            domain: Domain to rate limit
            
        Returns:
            Actual time waited in seconds
        """
        domain = domain.lower()
        required_delay = self.get_delay_for_domain(domain)
        
        with self._lock:
            last_request = self._last_request_times[domain]
            now = time.time()
            
            time_since_last = now - last_request
            wait_time = max(0, required_delay - time_since_last)
            
            if wait_time > 0:
                logger.debug(f"Rate limiting {domain}: waiting {wait_time:.2f}s")
                time.sleep(wait_time)
            
            # Update last request time
            self._last_request_times[domain] = time.time()
            
            return wait_time
    
    def record_request(self, domain: str) -> None:
        """Record that a request was made to a domain (without waiting)."""
        with self._lock:
            self._last_request_times[domain.lower()] = time.time()
    
    def get_time_until_allowed(self, domain: str) -> float:
        """
        Get time in seconds until next request is allowed for domain.
        
        Returns:
            Seconds until next request allowed (0 if allowed now)
        """
        domain = domain.lower()
        required_delay = self.get_delay_for_domain(domain)
        
        with self._lock:
            last_request = self._last_request_times[domain]
            time_since_last = time.time() - last_request
            return max(0, required_delay - time_since_last)
    
    def reset(self, domain: Optional[str] = None) -> None:
        """Reset rate limit tracking for a domain or all domains."""
        with self._lock:
            if domain:
                self._last_request_times.pop(domain.lower(), None)
            else:
                self._last_request_times.clear()


# Global rate limiter instance
_global_rate_limiter: Optional[DomainRateLimiter] = None


def get_rate_limiter(default_delay: float = 2.0) -> DomainRateLimiter:
    """Get or create the global rate limiter."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = DomainRateLimiter(default_delay=default_delay)
    return _global_rate_limiter


# =============================================================================
# Async Fetching with aiohttp
# =============================================================================

async def fetch_url_async(
    url: str,
    session,  # aiohttp.ClientSession
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Tuple[str, Optional[str], Optional[int], Optional[str]]:
    """
    Fetch a single URL asynchronously.
    
    Args:
        url: URL to fetch
        session: aiohttp ClientSession
        headers: Optional headers dict
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (url, html_content, status_code, error_message)
    """
    try:
        import aiohttp
        
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=True,
        ) as response:
            html = await response.text()
            return (url, html, response.status, None)
            
    except asyncio.TimeoutError:
        return (url, None, None, "Request timed out")
    except Exception as e:
        return (url, None, None, str(e))


async def fetch_urls_async(
    urls: List[str],
    headers: Optional[Dict[str, str]] = None,
    max_concurrent: int = 5,
    timeout: int = 30,
    rate_limiter: Optional[DomainRateLimiter] = None,
) -> List[Tuple[str, Optional[str], Optional[int], Optional[str]]]:
    """
    Fetch multiple URLs concurrently with rate limiting and SSRF protection.
    
    Args:
        urls: List of URLs to fetch
        headers: Optional headers dict
        max_concurrent: Maximum concurrent requests
        timeout: Request timeout in seconds
        rate_limiter: Optional rate limiter for per-domain delays
        
    Returns:
        List of tuples: (url, html_content, status_code, error_message)
    """
    try:
        import aiohttp
    except ImportError:
        logger.error("aiohttp not installed, falling back to sync fetching")
        return []
    
    # SSRF validation - filter out unsafe URLs
    try:
        from apps.core.security import validate_url_ssrf
        safe_urls = []
        unsafe_results = []
        for url in urls:
            is_safe, message = validate_url_ssrf(url)
            if is_safe:
                safe_urls.append(url)
            else:
                logger.warning(f"SSRF blocked for {url}: {message}")
                unsafe_results.append((url, None, None, f"SSRF blocked: {message}"))
        urls = safe_urls
    except ImportError:
        unsafe_results = []
    
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_limit(url: str, session) -> Tuple[str, Optional[str], Optional[int], Optional[str]]:
        async with semaphore:
            # Apply rate limiting per domain
            if rate_limiter:
                domain = urlparse(url).netloc
                # Note: This is a sync wait in async context - for true async,
                # you'd want an async rate limiter, but this works for moderate loads
                await asyncio.get_event_loop().run_in_executor(
                    None, rate_limiter.wait_if_needed, domain
                )
            
            return await fetch_url_async(url, session, headers, timeout)
    
    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=2)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_with_limit(url, session) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error tuples
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append((urls[i], None, None, str(result)))
            else:
                processed_results.append(result)
        
        # Add unsafe URL results
        processed_results.extend(unsafe_results)
        
        return processed_results


def fetch_urls_parallel(
    urls: List[str],
    headers: Optional[Dict[str, str]] = None,
    max_concurrent: int = 5,
    timeout: int = 30,
    rate_limiter: Optional[DomainRateLimiter] = None,
) -> List[Tuple[str, Optional[str], Optional[int], Optional[str]]]:
    """
    Synchronous wrapper for async URL fetching.
    
    Use this from synchronous code to fetch multiple URLs in parallel.
    
    Args:
        urls: List of URLs to fetch
        headers: Optional headers dict
        max_concurrent: Maximum concurrent requests
        timeout: Request timeout in seconds
        rate_limiter: Optional rate limiter for per-domain delays
        
    Returns:
        List of tuples: (url, html_content, status_code, error_message)
    """
    if not urls:
        return []
    
    try:
        import aiohttp
    except ImportError:
        logger.warning("aiohttp not installed, async fetching unavailable")
        return []
    
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, can't use run_until_complete
            # Fall back to thread-based execution
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    fetch_urls_async(urls, headers, max_concurrent, timeout, rate_limiter)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                fetch_urls_async(urls, headers, max_concurrent, timeout, rate_limiter)
            )
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(
            fetch_urls_async(urls, headers, max_concurrent, timeout, rate_limiter)
        )


# =============================================================================
# URL Deduplication Helper
# =============================================================================

class URLDeduplicator:
    """
    Tracks seen URLs with normalization to prevent duplicates.
    """
    
    def __init__(self, normalizer: Optional[URLNormalizer] = None):
        self.normalizer = normalizer or default_normalizer
        self._seen: set = set()
        self._lock = threading.Lock()
    
    def is_seen(self, url: str) -> bool:
        """Check if URL (or its normalized form) has been seen."""
        normalized = self.normalizer.normalize(url)
        with self._lock:
            return normalized in self._seen
    
    def add(self, url: str) -> bool:
        """
        Add URL to seen set.
        
        Returns:
            True if URL was new, False if already seen
        """
        normalized = self.normalizer.normalize(url)
        with self._lock:
            if normalized in self._seen:
                return False
            self._seen.add(normalized)
            return True
    
    def add_if_new(self, url: str) -> Optional[str]:
        """
        Add URL if not seen before.
        
        Returns:
            Normalized URL if new, None if duplicate
        """
        normalized = self.normalizer.normalize(url)
        with self._lock:
            if normalized in self._seen:
                return None
            self._seen.add(normalized)
            return normalized
    
    def count(self) -> int:
        """Get count of seen URLs."""
        with self._lock:
            return len(self._seen)
    
    def clear(self) -> None:
        """Clear all seen URLs."""
        with self._lock:
            self._seen.clear()
