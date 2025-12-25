"""
Pagination strategies for crawling.

Provides various pagination approaches:
- Parameter-based (?page=2)
- Path-based (/page/2)
- Next-link based (follow rel="next")
- Offset-based (?offset=20)
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..interfaces import PaginationResult, Paginator

logger = logging.getLogger(__name__)


class ParameterPaginator(Paginator):
    """
    Pagination using URL query parameters (e.g., ?page=2).
    
    This is the most common pagination style.
    """
    
    def __init__(
        self,
        param_name: str = 'page',
        start_page: int = 1,
        max_pages: int = 50,
    ):
        self.param_name = param_name
        self.start_page = start_page
        self.max_pages = max_pages
        self._current_page = start_page
    
    def next_page(
        self, 
        current_url: str,
        html: Optional[str] = None,
        response_meta: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """Generate next page URL using parameter increment."""
        # Check if we've hit max pages
        if self._current_page >= self.max_pages + self.start_page:
            return PaginationResult(
                url=None,
                page_number=self._current_page,
                has_more=False,
            )
        
        # Parse current URL
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        
        # Increment page
        self._current_page += 1
        params[self.param_name] = [str(self._current_page)]
        
        # Rebuild URL
        new_query = urlencode(params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            '',  # fragment
        ))
        
        return PaginationResult(
            url=new_url,
            page_number=self._current_page,
            has_more=True,
        )
    
    def reset(self):
        """Reset pagination state."""
        self._current_page = self.start_page
    
    def get_state(self) -> Dict[str, Any]:
        """Return current pagination state."""
        return {
            'type': 'parameter',
            'param_name': self.param_name,
            'current_page': self._current_page,
            'max_pages': self.max_pages,
        }


class PathPaginator(Paginator):
    """
    Pagination using URL path segments (e.g., /page/2/).
    
    Common in WordPress sites.
    """
    
    def __init__(
        self,
        pattern: str = '/page/{page}/',
        start_page: int = 1,
        max_pages: int = 50,
    ):
        """
        Args:
            pattern: URL pattern with {page} placeholder
            start_page: First page number
            max_pages: Maximum pages to crawl
        """
        self.pattern = pattern
        self.start_page = start_page
        self.max_pages = max_pages
        self._current_page = start_page
    
    def next_page(
        self, 
        current_url: str,
        html: Optional[str] = None,
        response_meta: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """Generate next page URL using path segment."""
        if self._current_page >= self.max_pages + self.start_page:
            return PaginationResult(
                url=None,
                page_number=self._current_page,
                has_more=False,
            )
        
        parsed = urlparse(current_url)
        
        # Remove existing page pattern from path
        path = parsed.path
        page_pattern = self.pattern.format(page=r'\d+')
        path = re.sub(page_pattern, '', path)
        
        # Increment page
        self._current_page += 1
        
        # Add new page segment
        page_segment = self.pattern.format(page=self._current_page)
        if not path.endswith('/'):
            path += '/'
        new_path = path.rstrip('/') + page_segment
        
        # Rebuild URL
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            new_path,
            '',
            '',
            '',
        ))
        
        return PaginationResult(
            url=new_url,
            page_number=self._current_page,
            has_more=True,
        )
    
    def reset(self):
        """Reset pagination state."""
        self._current_page = self.start_page
    
    def get_state(self) -> Dict[str, Any]:
        """Return current pagination state."""
        return {
            'type': 'path',
            'pattern': self.pattern,
            'current_page': self._current_page,
            'max_pages': self.max_pages,
        }


class NextLinkPaginator(Paginator):
    """
    Pagination by following "next" links in HTML.
    
    Looks for:
    - <link rel="next" href="...">
    - <a rel="next" href="...">
    - Links with text like "Next", ">>", etc.
    """
    
    NEXT_TEXT_PATTERNS = [
        'next', 'tiếp theo', '»', '>>', 'older',
        'next page', 'load more', 'xem thêm',
    ]
    
    def __init__(
        self,
        max_pages: int = 50,
        next_text_patterns: Optional[List[str]] = None,
    ):
        self.max_pages = max_pages
        self.next_patterns = next_text_patterns or self.NEXT_TEXT_PATTERNS
        self._pages_crawled = 0
    
    def next_page(
        self, 
        current_url: str,
        html: Optional[str] = None,
        response_meta: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """Find next page URL from HTML content."""
        self._pages_crawled += 1
        
        if self._pages_crawled >= self.max_pages:
            return PaginationResult(
                url=None,
                page_number=self._pages_crawled,
                has_more=False,
            )
        
        if not html:
            return PaginationResult(
                url=None,
                page_number=self._pages_crawled,
                has_more=False,
            )
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try link rel="next"
            link_next = soup.find('link', rel='next')
            if link_next and link_next.get('href'):
                next_url = urljoin(current_url, link_next['href'])
                return PaginationResult(
                    url=next_url,
                    page_number=self._pages_crawled + 1,
                    has_more=True,
                )
            
            # Try a rel="next"
            a_next = soup.find('a', rel='next')
            if a_next and a_next.get('href'):
                next_url = urljoin(current_url, a_next['href'])
                return PaginationResult(
                    url=next_url,
                    page_number=self._pages_crawled + 1,
                    has_more=True,
                )
            
            # Try finding link with "next" text
            for pattern in self.next_patterns:
                next_link = soup.find('a', string=lambda t: t and pattern.lower() in t.lower())
                if next_link and next_link.get('href'):
                    next_url = urljoin(current_url, next_link['href'])
                    return PaginationResult(
                        url=next_url,
                        page_number=self._pages_crawled + 1,
                        has_more=True,
                    )
            
            # No next link found
            return PaginationResult(
                url=None,
                page_number=self._pages_crawled,
                has_more=False,
            )
            
        except Exception as e:
            logger.error(f"Error finding next page: {e}")
            return PaginationResult(
                url=None,
                page_number=self._pages_crawled,
                has_more=False,
            )
    
    def reset(self):
        """Reset pagination state."""
        self._pages_crawled = 0
    
    def get_state(self) -> Dict[str, Any]:
        """Return current pagination state."""
        return {
            'type': 'next_link',
            'pages_crawled': self._pages_crawled,
            'max_pages': self.max_pages,
        }


class OffsetPaginator(Paginator):
    """
    Pagination using offset parameter (e.g., ?offset=20).
    
    Common in API-style pagination.
    """
    
    def __init__(
        self,
        param_name: str = 'offset',
        items_per_page: int = 20,
        max_offset: int = 1000,
    ):
        self.param_name = param_name
        self.items_per_page = items_per_page
        self.max_offset = max_offset
        self._current_offset = 0
    
    def next_page(
        self, 
        current_url: str,
        html: Optional[str] = None,
        response_meta: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """Generate next page URL using offset increment."""
        # Move to next offset
        self._current_offset += self.items_per_page
        
        if self._current_offset >= self.max_offset:
            return PaginationResult(
                url=None,
                page_number=self._current_offset // self.items_per_page,
                has_more=False,
            )
        
        # Parse current URL
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        
        # Set offset
        params[self.param_name] = [str(self._current_offset)]
        
        # Rebuild URL
        new_query = urlencode(params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            '',
        ))
        
        return PaginationResult(
            url=new_url,
            page_number=self._current_offset // self.items_per_page,
            has_more=True,
        )
    
    def reset(self):
        """Reset pagination state."""
        self._current_offset = 0
    
    def get_state(self) -> Dict[str, Any]:
        """Return current pagination state."""
        return {
            'type': 'offset',
            'param_name': self.param_name,
            'current_offset': self._current_offset,
            'items_per_page': self.items_per_page,
            'max_offset': self.max_offset,
        }


class AdaptivePaginator(Paginator):
    """
    Smart paginator that auto-detects pagination style.
    
    Tries strategies in order:
    1. Look for rel="next" link
    2. Look for page parameter in URL
    3. Look for pagination pattern in HTML
    4. Fall back to parameter-based pagination
    """
    
    PAGE_PARAMS = ['page', 'p', 'pg', 'pagenum', 'pn', 'trang']
    
    def __init__(self, max_pages: int = 50):
        self.max_pages = max_pages
        self._detected_strategy: Optional[Paginator] = None
        self._pages_crawled = 0
    
    def _detect_strategy(self, url: str, html: str) -> Paginator:
        """Auto-detect the best pagination strategy."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Check if URL has a page parameter
        for param in self.PAGE_PARAMS:
            if param in params:
                return ParameterPaginator(
                    param_name=param,
                    start_page=int(params[param][0]) if params[param] else 1,
                    max_pages=self.max_pages,
                )
        
        # Check for path-based pagination
        if re.search(r'/page/\d+', parsed.path):
            return PathPaginator(max_pages=self.max_pages)
        
        # Check HTML for next link
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            if soup.find('link', rel='next') or soup.find('a', rel='next'):
                return NextLinkPaginator(max_pages=self.max_pages)
        
        # Default to parameter-based
        return ParameterPaginator(max_pages=self.max_pages)
    
    def next_page(
        self, 
        current_url: str,
        html: Optional[str] = None,
        response_meta: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """Detect strategy and get next page."""
        self._pages_crawled += 1
        
        if self._pages_crawled >= self.max_pages:
            return PaginationResult(
                url=None,
                page_number=self._pages_crawled,
                has_more=False,
            )
        
        # Detect strategy on first call
        if not self._detected_strategy and html:
            self._detected_strategy = self._detect_strategy(current_url, html)
            logger.info(f"Detected pagination strategy: {type(self._detected_strategy).__name__}")
        
        # Use detected strategy
        if self._detected_strategy:
            return self._detected_strategy.next_page(current_url, html, response_meta)
        
        return PaginationResult(
            url=None,
            page_number=self._pages_crawled,
            has_more=False,
        )
    
    def reset(self):
        """Reset pagination state."""
        self._detected_strategy = None
        self._pages_crawled = 0
    
    def get_state(self) -> Dict[str, Any]:
        """Return current pagination state."""
        inner_state = {}
        if self._detected_strategy:
            inner_state = self._detected_strategy.get_state()
        
        return {
            'type': 'adaptive',
            'pages_crawled': self._pages_crawled,
            'max_pages': self.max_pages,
            'detected_strategy': inner_state,
        }


def create_paginator(
    strategy: str = 'adaptive',
    **kwargs
) -> Paginator:
    """
    Factory function to create paginators.
    
    Args:
        strategy: One of 'parameter', 'path', 'next_link', 'offset', 'adaptive'
        **kwargs: Additional arguments for the paginator
    
    Returns:
        Paginator instance
    """
    strategies = {
        'parameter': ParameterPaginator,
        'path': PathPaginator,
        'next_link': NextLinkPaginator,
        'offset': OffsetPaginator,
        'adaptive': AdaptivePaginator,
    }
    
    if strategy not in strategies:
        raise ValueError(f"Unknown pagination strategy: {strategy}")
    
    return strategies[strategy](**kwargs)
