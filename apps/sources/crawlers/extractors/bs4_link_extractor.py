"""
BeautifulSoup-based link extractor implementation.

This is the default link extractor using BeautifulSoup for HTML parsing.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..interfaces import ExtractedLink, LinkExtractor

logger = logging.getLogger(__name__)


class BS4LinkExtractor(LinkExtractor):
    """
    Link extractor using BeautifulSoup.
    
    Features:
    - Extracts all links from HTML
    - Resolves relative URLs
    - Filters by domain
    - Heuristic article detection
    - Configurable via rules
    """
    
    # Common non-article URL patterns
    EXCLUDE_PATTERNS = [
        '/category/', '/tag/', '/author/', '/page/',
        '/search/', '/archive/', '/about', '/contact',
        '/login', '/register', '/subscribe', '/privacy',
        '/terms', '/cookie', '/sitemap', '/feed',
        '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
        '.xml', '.json', '.zip', '.mp3', '.mp4',
    ]
    
    # Common article URL patterns
    INCLUDE_PATTERNS = [
        '/article/', '/post/', '/news/', '/blog/',
        '/story/', '/analysis/', '/report/', '/feature/',
        '/opinion/', '/editorial/', '/review/',
    ]
    
    def __init__(
        self,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        min_path_segments: int = 2,
    ):
        self.exclude_patterns = exclude_patterns or self.EXCLUDE_PATTERNS
        self.include_patterns = include_patterns or self.INCLUDE_PATTERNS
        self.min_path_segments = min_path_segments
    
    def extract_links(
        self, 
        html: str, 
        base_url: str,
        domain: Optional[str] = None
    ) -> List[ExtractedLink]:
        """
        Extract all links from HTML content.
        """
        if not html:
            return []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            links = []
            
            for anchor in soup.find_all('a', href=True):
                href = anchor['href'].strip()
                
                # Skip empty or javascript links
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    continue
                
                # Resolve to absolute URL
                full_url = urljoin(base_url, href)
                
                # Parse URL
                parsed = urlparse(full_url)
                
                # Skip non-HTTP URLs
                if parsed.scheme not in ('http', 'https'):
                    continue
                
                # Filter by domain if specified
                if domain and parsed.netloc.lower() != domain.lower():
                    continue
                
                # Get link text and context
                link_text = anchor.get_text(strip=True)[:200] if anchor.get_text(strip=True) else None
                
                # Get title attribute as context
                context = anchor.get('title', '')[:200] if anchor.get('title') else None
                
                links.append(ExtractedLink(
                    url=full_url,
                    text=link_text,
                    context=context,
                    is_article=False,  # Will be set by filter_article_links
                    confidence=0.0,
                ))
            
            # Deduplicate by URL
            seen = set()
            unique_links = []
            for link in links:
                if link.url not in seen:
                    seen.add(link.url)
                    unique_links.append(link)
            
            return unique_links
            
        except Exception as e:
            logger.error(f"Error extracting links: {e}")
            return []
    
    def filter_article_links(
        self, 
        links: List[ExtractedLink],
        rules: Optional[Dict[str, Any]] = None
    ) -> List[ExtractedLink]:
        """
        Filter links to identify likely articles.
        """
        rules = rules or {}
        
        # Get custom patterns from rules
        custom_include = rules.get('include_patterns', [])
        custom_exclude = rules.get('exclude_patterns', [])
        required_ext = rules.get('require_extensions', [])
        
        article_links = []
        
        for link in links:
            url_lower = link.url.lower()
            
            # Check custom exclude patterns first
            if custom_exclude and any(p.lower() in url_lower for p in custom_exclude):
                continue
            
            # Check required extensions
            if required_ext:
                if not any(url_lower.endswith(ext.lower()) for ext in required_ext):
                    continue
            
            # Check custom include patterns
            if custom_include:
                if not any(p.lower() in url_lower for p in custom_include):
                    continue
                # If passes custom include, mark as article
                link.is_article = True
                link.confidence = 0.8
                article_links.append(link)
                continue
            
            # Apply default exclude patterns
            if any(pattern in url_lower for pattern in self.exclude_patterns):
                continue
            
            # Check default include patterns
            confidence = 0.3
            if any(pattern in url_lower for pattern in self.include_patterns):
                confidence = 0.7
            
            # Check path depth as heuristic
            parsed = urlparse(link.url)
            path_segments = [s for s in parsed.path.split('/') if s]
            
            if len(path_segments) >= self.min_path_segments:
                confidence += 0.2
            
            # Check if link text looks like a headline
            if link.text and len(link.text) > 30:
                confidence += 0.1
            
            if confidence >= 0.4:
                link.is_article = True
                link.confidence = min(1.0, confidence)
                article_links.append(link)
        
        return article_links
    
    def extract_metadata(self, html: str) -> Dict[str, Any]:
        """
        Extract page metadata (title, description, etc.).
        
        Useful for article content extraction.
        """
        metadata = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                metadata['title'] = og_title['content']
            elif soup.find('h1'):
                metadata['title'] = soup.find('h1').get_text(strip=True)
            elif soup.find('title'):
                metadata['title'] = soup.find('title').get_text(strip=True)
            
            # Description
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                metadata['description'] = og_desc['content']
            else:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    metadata['description'] = meta_desc['content']
            
            # Author
            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta and author_meta.get('content'):
                metadata['author'] = author_meta['content']
            
            # Published date
            date_meta = soup.find('meta', property='article:published_time')
            if date_meta and date_meta.get('content'):
                metadata['published_date'] = date_meta['content']
            
            # Image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                metadata['image'] = og_image['content']
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return metadata
