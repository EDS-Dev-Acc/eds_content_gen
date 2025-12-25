"""
Discovery Connectors for seed URL discovery.

Phase 16: Multiple discovery channels with capture-first approach.

Connectors:
- SERPConnector: Web search API (stubbed, requires SERP_API_KEY)
- RSSConnector: RSS/Atom feed parsing
- HTMLDirectoryConnector: HTML page link extraction for directories

All connectors:
- Return candidate URLs only (no deep extraction)
- Respect SSRF guards and rate limits
- Support controlled fetch with raw capture
"""

import gzip
import hashlib
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin

from django.conf import settings
from django.utils import timezone

from apps.core.security import SSRFGuard, SafeHTTPClient, URLNormalizer
from apps.sources.crawlers.utils import DomainRateLimiter, get_rate_limiter

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CandidateURL:
    """A discovered URL candidate with metadata."""
    url: str
    normalized_url: str = ''
    domain: str = ''
    discovery_method: str = ''
    query_used: str = ''
    referrer_url: str = ''
    title: str = ''
    snippet: str = ''
    position: int = 0  # SERP position or link order
    confidence: int = 50
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.normalized_url and self.url:
            try:
                self.normalized_url = URLNormalizer.normalize(self.url)
            except Exception:
                self.normalized_url = self.url
        if not self.domain and self.url:
            try:
                self.domain = urlparse(self.url).netloc
            except Exception:
                pass


@dataclass
class RawCapture:
    """Raw HTTP response capture for audit and later extraction."""
    url: str
    final_url: str
    status_code: int
    headers: Dict[str, str]
    body_hash: str  # SHA-256 of raw body
    body_size: int
    body_path: Optional[str] = None  # File path if stored externally
    body_compressed: Optional[bytes] = None  # Gzipped body if inline (small)
    content_type: str = ''
    fetch_timestamp: datetime = field(default_factory=timezone.now)
    fetch_mode: str = 'static'  # static, rendered, api
    discovery_run_id: Optional[str] = None
    error: Optional[str] = None
    
    # Size thresholds
    MAX_INLINE_SIZE = 50 * 1024  # 50KB inline, larger goes to file
    MAX_CAPTURE_SIZE = 500 * 1024  # 500KB max total
    
    @classmethod
    def from_response(
        cls,
        url: str,
        response,  # requests.Response
        fetch_mode: str = 'static',
        discovery_run_id: Optional[str] = None,
    ) -> 'RawCapture':
        """Create capture from requests Response object."""
        body = response.content or b''
        body_size = len(body)
        
        # Truncate if too large
        if body_size > cls.MAX_CAPTURE_SIZE:
            body = body[:cls.MAX_CAPTURE_SIZE]
            body_size = cls.MAX_CAPTURE_SIZE
        
        body_hash = hashlib.sha256(body).hexdigest()
        
        # Compress body
        compressed = gzip.compress(body, compresslevel=6)
        
        # Decide storage: inline if small enough
        body_compressed = compressed if len(compressed) <= cls.MAX_INLINE_SIZE else None
        body_path = None  # External storage handled by caller
        
        headers = dict(response.headers) if response.headers else {}
        
        return cls(
            url=url,
            final_url=str(response.url) if response.url else url,
            status_code=response.status_code,
            headers=headers,
            body_hash=body_hash,
            body_size=body_size,
            body_compressed=body_compressed,
            body_path=body_path,
            content_type=response.headers.get('Content-Type', ''),
            fetch_mode=fetch_mode,
            discovery_run_id=discovery_run_id,
        )
    
    def get_body(self) -> bytes:
        """Get decompressed body content."""
        if self.body_compressed:
            return gzip.decompress(self.body_compressed)
        elif self.body_path:
            try:
                import os
                from django.conf import settings
                full_path = os.path.join(settings.MEDIA_ROOT, 'captures', self.body_path)
                with open(full_path, 'rb') as f:
                    return gzip.decompress(f.read())
            except Exception as e:
                logger.error(f"Failed to read capture file {self.body_path}: {e}")
                return b''
        return b''


# =============================================================================
# Base Connector
# =============================================================================

class BaseConnector(ABC):
    """
    Abstract base class for discovery connectors.
    
    All connectors must:
    - Return CandidateURL objects (not deep extraction)
    - Respect SSRF guards via SafeHTTPClient
    - Use rate limiting via DomainRateLimiter
    - Support controlled fetch with RawCapture
    """
    
    def __init__(
        self,
        rate_limiter: Optional[DomainRateLimiter] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.http_client = SafeHTTPClient(
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name for logging and metrics."""
        pass
    
    @abstractmethod
    def discover(
        self,
        query: str,
        max_results: int = 50,
        **kwargs
    ) -> Tuple[List[CandidateURL], List[RawCapture]]:
        """
        Discover candidate URLs for the given query.
        
        Args:
            query: Search query or target URL
            max_results: Maximum candidates to return
            **kwargs: Connector-specific options
            
        Returns:
            Tuple of (candidates, captures) - captures for audit trail
        """
        pass
    
    def _fetch_with_capture(
        self,
        url: str,
        fetch_mode: str = 'static',
        discovery_run_id: Optional[str] = None,
    ) -> Tuple[Optional[RawCapture], Optional[str]]:
        """
        Fetch URL with SSRF protection and capture response.
        
        Returns:
            Tuple of (capture, error_message)
        """
        try:
            # Rate limit
            domain = urlparse(url).netloc
            self.rate_limiter.wait_if_needed(domain)
            
            # Fetch via SafeHTTPClient (SSRF protected)
            response = self.http_client.get(url)
            
            # Record rate limit
            self.rate_limiter.record_request(domain)
            
            # Create capture
            capture = RawCapture.from_response(
                url=url,
                response=response,
                fetch_mode=fetch_mode,
                discovery_run_id=discovery_run_id,
            )
            
            return capture, None
            
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None, str(e)


# =============================================================================
# SERP Connector (Stub - requires API key)
# =============================================================================

class SERPConnector(BaseConnector):
    """
    Web search API connector for broad discovery.
    
    Currently a stub - requires SERP_API_KEY to function.
    Supports multiple providers: Google, Bing, DuckDuckGo via APIs.
    """
    
    name = 'serp'
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = 'google',
        **kwargs
    ):
        super().__init__(**kwargs)
        self.api_key = api_key or getattr(settings, 'SERP_API_KEY', None)
        self.provider = provider
    
    @property
    def available(self) -> bool:
        """Check if SERP API is configured."""
        return bool(self.api_key)
    
    def discover(
        self,
        query: str,
        max_results: int = 50,
        country: str = '',
        language: str = 'en',
        **kwargs
    ) -> Tuple[List[CandidateURL], List[RawCapture]]:
        """
        Search web for candidate URLs.
        
        Without API key, returns empty results with warning.
        """
        candidates = []
        captures = []
        
        if not self.available:
            logger.warning(
                "SERP connector not configured - set SERP_API_KEY. "
                "Returning empty results."
            )
            return candidates, captures
        
        # TODO: Implement actual SERP API calls
        # For now, this is a stub that would call:
        # - Google Custom Search API
        # - Bing Web Search API  
        # - SerpApi service
        
        logger.info(f"SERP search: query='{query}', max={max_results}")
        
        # Stub: Return empty for now
        # Real implementation would:
        # 1. Call SERP API with query
        # 2. Parse results into CandidateURL objects
        # 3. Optionally fetch each result page for capture
        
        return candidates, captures


# =============================================================================
# RSS Connector
# =============================================================================

class RSSConnector(BaseConnector):
    """
    RSS/Atom feed connector for news and publication discovery.
    
    Parses feed entries to discover article and source URLs.
    """
    
    name = 'rss'
    
    def discover(
        self,
        query: str,  # URL of RSS feed
        max_results: int = 50,
        extract_sources: bool = True,
        **kwargs
    ) -> Tuple[List[CandidateURL], List[RawCapture]]:
        """
        Parse RSS/Atom feed and extract candidate URLs.
        
        Args:
            query: Feed URL to parse
            max_results: Max entries to process
            extract_sources: If True, also extract source domains from entries
        """
        candidates = []
        captures = []
        
        # Validate URL
        if not query.startswith(('http://', 'https://')):
            logger.warning(f"Invalid feed URL: {query}")
            return candidates, captures
        
        # Fetch feed with capture
        capture, error = self._fetch_with_capture(
            url=query,
            fetch_mode='static',
        )
        
        if error or not capture:
            logger.warning(f"Failed to fetch feed {query}: {error}")
            return candidates, captures
        
        captures.append(capture)
        
        # Parse feed
        body = capture.get_body()
        if not body:
            return candidates, captures
        
        try:
            candidates = self._parse_feed(
                body.decode('utf-8', errors='replace'),
                feed_url=query,
                max_results=max_results,
                extract_sources=extract_sources,
            )
        except Exception as e:
            logger.error(f"Failed to parse feed {query}: {e}")
        
        return candidates, captures
    
    def _parse_feed(
        self,
        content: str,
        feed_url: str,
        max_results: int,
        extract_sources: bool,
    ) -> List[CandidateURL]:
        """Parse RSS/Atom feed content."""
        candidates = []
        seen_domains = set()
        
        # Simple regex-based parsing (avoid heavy feedparser dependency)
        # Look for <link> and <guid> tags
        link_patterns = [
            r'<link[^>]*>([^<]+)</link>',
            r'<link[^>]*href=["\']([^"\']+)["\']',
            r'<guid[^>]*>([^<]+)</guid>',
        ]
        
        position = 0
        for pattern in link_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                if position >= max_results:
                    break
                
                url = match.group(1).strip()
                if not url or not url.startswith(('http://', 'https://')):
                    continue
                
                # Skip feed URL itself
                if url == feed_url:
                    continue
                
                domain = urlparse(url).netloc
                
                # Skip if we've seen this domain and only extracting sources
                if extract_sources and domain in seen_domains:
                    continue
                
                seen_domains.add(domain)
                position += 1
                
                candidates.append(CandidateURL(
                    url=url,
                    domain=domain,
                    discovery_method='rss',
                    referrer_url=feed_url,
                    position=position,
                    confidence=60,  # Medium confidence from RSS
                ))
        
        return candidates


# =============================================================================
# HTML Directory Connector
# =============================================================================

class HTMLDirectoryConnector(BaseConnector):
    """
    HTML page connector for extracting links from directories and lists.
    
    Useful for:
    - Association member lists
    - Industry directories
    - Government registries
    - Company listing pages
    """
    
    name = 'html_directory'
    
    # Patterns for directory/list indicators
    LIST_INDICATORS = [
        r'members?',
        r'directory',
        r'companies',
        r'list',
        r'registry',
        r'partners?',
        r'suppliers?',
        r'vendors?',
        r'associations?',
    ]
    
    def discover(
        self,
        query: str,  # URL of directory page
        max_results: int = 100,
        same_domain_only: bool = False,
        link_pattern: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[CandidateURL], List[RawCapture]]:
        """
        Extract candidate URLs from HTML directory page.
        
        Args:
            query: Directory page URL
            max_results: Max links to extract
            same_domain_only: Only extract same-domain links
            link_pattern: Optional regex to filter links
        """
        candidates = []
        captures = []
        
        # Validate URL
        if not query.startswith(('http://', 'https://')):
            logger.warning(f"Invalid directory URL: {query}")
            return candidates, captures
        
        # Fetch page with capture
        capture, error = self._fetch_with_capture(
            url=query,
            fetch_mode='static',
        )
        
        if error or not capture:
            logger.warning(f"Failed to fetch directory {query}: {error}")
            return candidates, captures
        
        captures.append(capture)
        
        # Parse HTML
        body = capture.get_body()
        if not body:
            return candidates, captures
        
        try:
            candidates = self._extract_links(
                body.decode('utf-8', errors='replace'),
                page_url=query,
                max_results=max_results,
                same_domain_only=same_domain_only,
                link_pattern=link_pattern,
            )
        except Exception as e:
            logger.error(f"Failed to parse directory {query}: {e}")
        
        return candidates, captures
    
    def _extract_links(
        self,
        content: str,
        page_url: str,
        max_results: int,
        same_domain_only: bool,
        link_pattern: Optional[str],
    ) -> List[CandidateURL]:
        """Extract links from HTML content."""
        candidates = []
        seen_urls = set()
        page_domain = urlparse(page_url).netloc
        
        # Extract all href links
        href_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        
        position = 0
        for match in re.finditer(href_pattern, content, re.IGNORECASE | re.DOTALL):
            if position >= max_results:
                break
            
            href = match.group(1).strip()
            text = match.group(2).strip()
            
            # Skip empty, anchor, javascript links
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Resolve relative URLs
            if not href.startswith(('http://', 'https://')):
                href = urljoin(page_url, href)
            
            # Validate URL
            try:
                parsed = urlparse(href)
                if not parsed.netloc:
                    continue
            except Exception:
                continue
            
            # Apply same-domain filter
            if same_domain_only and parsed.netloc != page_domain:
                continue
            
            # Apply custom link pattern
            if link_pattern:
                if not re.search(link_pattern, href, re.IGNORECASE):
                    continue
            
            # Normalize and dedupe
            try:
                normalized = URLNormalizer.normalize(href)
            except Exception:
                normalized = href
            
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            
            position += 1
            
            # Calculate confidence based on context
            confidence = self._calculate_link_confidence(href, text, content)
            
            candidates.append(CandidateURL(
                url=href,
                normalized_url=normalized,
                domain=parsed.netloc,
                discovery_method='html_directory',
                referrer_url=page_url,
                title=text[:200] if text else '',
                position=position,
                confidence=confidence,
            ))
        
        return candidates
    
    def _calculate_link_confidence(
        self,
        url: str,
        text: str,
        page_content: str,
    ) -> int:
        """Calculate confidence score based on link context."""
        confidence = 50  # Base confidence
        
        # Boost for external domains (likely companies/sources)
        if urlparse(url).netloc not in page_content[:500]:
            confidence += 10
        
        # Boost for descriptive anchor text
        if text and len(text) > 10:
            confidence += 5
        
        # Boost for company-related keywords in text
        company_keywords = ['company', 'ltd', 'inc', 'corp', 'llc', 'co.']
        if any(kw in text.lower() for kw in company_keywords):
            confidence += 10
        
        # Cap at 100
        return min(confidence, 100)


# =============================================================================
# Connector Factory
# =============================================================================

def get_connector(
    connector_type: str,
    **kwargs
) -> BaseConnector:
    """
    Get a connector by type.
    
    Args:
        connector_type: 'serp', 'rss', 'html_directory'
        **kwargs: Connector-specific options
        
    Returns:
        Configured connector instance
    """
    connectors = {
        'serp': SERPConnector,
        'rss': RSSConnector,
        'html_directory': HTMLDirectoryConnector,
    }
    
    if connector_type not in connectors:
        raise ValueError(f"Unknown connector type: {connector_type}")
    
    return connectors[connector_type](**kwargs)
