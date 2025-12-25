"""
Crawler interfaces (abstract base classes) for EMCIP.

These interfaces define the contract for pluggable components:
- Fetcher: Retrieve HTML content from URLs
- LinkExtractor: Extract article links from HTML
- Paginator: Handle pagination logic

Implementations can be swapped without changing the crawler logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class FetcherType(str, Enum):
    """Supported fetcher backends."""
    HTTP = "http"
    BROWSER = "browser"
    HYBRID = "hybrid"


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    url: str
    html: Optional[str] = None
    status_code: Optional[int] = None
    final_url: Optional[str] = None  # After redirects
    error: Optional[str] = None
    fetcher_type: str = "http"
    fetch_time_ms: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.html is not None and self.error is None


@dataclass
class ExtractedLink:
    """A link extracted from a page."""
    url: str
    text: Optional[str] = None
    context: Optional[str] = None  # Surrounding text/title
    is_article: bool = False
    confidence: float = 0.0


@dataclass
class PaginationResult:
    """Result of pagination detection."""
    url: Optional[str] = None  # Next page URL, None if no more pages
    page_number: Optional[int] = None
    has_more: bool = False
    total_pages: Optional[int] = None
    pagination_type: str = "unknown"


class Fetcher(ABC):
    """
    Abstract base class for content fetchers.
    
    Fetchers are responsible for retrieving HTML content from URLs,
    handling headers, timeouts, and error conditions.
    """
    
    @property
    @abstractmethod
    def fetcher_type(self) -> FetcherType:
        """Return the type of this fetcher."""
        pass
    
    @abstractmethod
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """
        Fetch content from a URL.
        
        Args:
            url: The URL to fetch
            headers: Optional custom headers
            
        Returns:
            FetchResult with content or error
        """
        pass
    
    @abstractmethod
    def fetch_many(
        self, 
        urls: List[str], 
        headers: Optional[Dict[str, str]] = None,
        max_concurrent: int = 5
    ) -> List[FetchResult]:
        """
        Fetch multiple URLs, potentially in parallel.
        
        Args:
            urls: List of URLs to fetch
            headers: Optional custom headers
            max_concurrent: Max concurrent requests
            
        Returns:
            List of FetchResults in same order as input URLs
        """
        pass
    
    def close(self) -> None:
        """Clean up resources (override if needed)."""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class LinkExtractor(ABC):
    """
    Abstract base class for link extraction.
    
    LinkExtractors parse HTML and identify links that may be articles.
    """
    
    @abstractmethod
    def extract_links(
        self, 
        html: str, 
        base_url: str,
        domain: Optional[str] = None
    ) -> List[ExtractedLink]:
        """
        Extract links from HTML content.
        
        Args:
            html: HTML content to parse
            base_url: Base URL for resolving relative links
            domain: Optional domain for filtering
            
        Returns:
            List of extracted links
        """
        pass
    
    @abstractmethod
    def filter_article_links(
        self, 
        links: List[ExtractedLink],
        rules: Optional[Dict[str, Any]] = None
    ) -> List[ExtractedLink]:
        """
        Filter links to identify likely articles.
        
        Args:
            links: List of extracted links
            rules: Optional site-specific rules
            
        Returns:
            Filtered list of article links
        """
        pass


class Paginator(ABC):
    """
    Abstract base class for pagination handling.
    
    Paginators detect and generate pagination URLs for multi-page crawls.
    """
    
    @abstractmethod
    def next_page(
        self, 
        current_url: str,
        html: Optional[str] = None,
        response_meta: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """
        Get the next page URL.
        
        Args:
            current_url: Current page URL
            html: Optional HTML content (for next-link detection)
            response_meta: Optional response metadata
            
        Returns:
            PaginationResult with next page info
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset pagination state to initial values."""
        pass
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Return current pagination state for debugging/persistence."""
        pass


class CrawlerPipeline:
    """
    Orchestrates fetching, extraction, and pagination.
    
    This class composes the interfaces to provide the full crawl pipeline.
    """
    
    def __init__(
        self,
        fetcher: Fetcher,
        link_extractor: LinkExtractor,
        paginator: Paginator,
    ):
        self.fetcher = fetcher
        self.link_extractor = link_extractor
        self.paginator = paginator
    
    def run(
        self,
        url: str,
        domain: Optional[str] = None,
        max_pages: int = 3,
        rules: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Run the crawl pipeline.
        
        Args:
            url: Starting URL
            domain: Domain being crawled (auto-detected if not provided)
            max_pages: Maximum pages to crawl
            rules: Site-specific rules
            headers: Custom headers
            
        Returns:
            Dict with crawl results
        """
        from urllib.parse import urlparse
        
        if domain is None:
            domain = urlparse(url).netloc
        
        article_urls = []
        seen_urls = set()
        current_url = url
        pages_crawled = 0
        errors = []
        
        # Reset paginator state
        self.paginator.reset()
        
        while pages_crawled < max_pages:
            # Fetch the page
            result = self.fetcher.fetch(current_url, headers)
            if not result.success:
                errors.append(f"Failed to fetch {current_url}: {result.error}")
                break
            
            pages_crawled += 1
            
            # Extract links
            links = self.link_extractor.extract_links(
                result.html, 
                result.final_url or current_url,
                domain
            )
            
            # Filter to articles
            article_links = self.link_extractor.filter_article_links(links, rules)
            
            # Add new URLs
            new_count = 0
            for link in article_links:
                if link.url not in seen_urls:
                    seen_urls.add(link.url)
                    article_urls.append(link.url)
                    new_count += 1
            
            # Stop if no new articles found
            if new_count == 0 and pages_crawled > 1:
                break
            
            # Check for next page
            pagination = self.paginator.next_page(
                current_url,
                html=result.html,
            )
            
            if not pagination.has_more or not pagination.url:
                break
            
            current_url = pagination.url
        
        return {
            'article_urls': article_urls,
            'total_links': len(article_urls),
            'article_links': len(article_links) if article_links else 0,
            'pages_crawled': pages_crawled,
            'errors': errors,
        }
    
    # Alias for backwards compatibility
    crawl_listing = run
