"""
Lightweight Seed Classifier for captured content.

Phase 16: Classifies pages from captured HTML without heavy extraction.

Signals extracted:
- Page type (directory, company homepage, association, gov registry, news)
- Presence of contact/about pages
- Sitemap and RSS feed detection
- Language and country indicators
- Topical keyword presence
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of page classification."""
    
    # Page type classification
    page_type: str = 'unknown'  # directory, company_homepage, association, gov_registry, news, marketplace
    page_type_confidence: int = 50
    
    # Entity type detection
    entity_type: str = 'unknown'  # logistics_company, freight_forwarder, etc.
    entity_type_confidence: int = 50
    
    # Geographic signals
    country_codes: List[str] = field(default_factory=list)
    detected_languages: List[str] = field(default_factory=list)
    
    # Structure signals
    has_contact_page: bool = False
    has_about_page: bool = False
    has_sitemap: bool = False
    has_rss_feed: bool = False
    has_member_list: bool = False
    has_pagination: bool = False
    
    # Content signals
    link_count: int = 0
    external_link_count: int = 0
    form_count: int = 0
    
    # Discovered entrypoints
    sitemap_urls: List[str] = field(default_factory=list)
    feed_urls: List[str] = field(default_factory=list)
    list_page_urls: List[str] = field(default_factory=list)
    
    # Raw signals for scoring
    signals: Dict[str, Any] = field(default_factory=dict)


class SeedClassifier:
    """
    Lightweight classifier for captured HTML content.
    
    Extracts classification signals without heavy parsing libraries.
    CPU-efficient for use in shared worker pools.
    """
    
    # Page type indicators
    PAGE_TYPE_PATTERNS = {
        'directory': [
            r'directory',
            r'listing',
            r'companies?\s+list',
            r'business\s+directory',
            r'yellow\s*pages',
            r'find\s+(?:a\s+)?compan',
        ],
        'association': [
            r'association',
            r'member(?:s|ship)',
            r'federation',
            r'council',
            r'chamber\s+of',
            r'industry\s+(?:body|group)',
        ],
        'gov_registry': [
            r'government',
            r'registry',
            r'official',
            r'ministry',
            r'\.gov\.',
            r'license',
            r'registration',
        ],
        'news': [
            r'news',
            r'article',
            r'press\s+release',
            r'latest',
            r'published',
            r'by\s+\w+\s+(?:on|at)\s+\d',
        ],
        'marketplace': [
            r'marketplace',
            r'buy(?:ing)?',
            r'sell(?:ing)?',
            r'quote',
            r'rfq',
            r'supplier',
        ],
        'company_homepage': [
            r'about\s+us',
            r'our\s+services',
            r'contact\s+us',
            r'our\s+company',
            r'who\s+we\s+are',
        ],
    }
    
    # Entity type indicators (logistics focus)
    ENTITY_TYPE_PATTERNS = {
        'logistics_company': [
            r'logistics',
            r'supply\s*chain',
            r'distribution',
        ],
        'freight_forwarder': [
            r'freight\s*forward',
            r'forwarding',
            r'customs\s*broker',
            r'cargo',
        ],
        'port_operator': [
            r'port\s*(?:operator|authority|terminal)',
            r'terminal\s*operator',
            r'container\s*terminal',
        ],
        'trucking': [
            r'truck(?:ing)?',
            r'road\s*freight',
            r'haulage',
            r'transport(?:ation)?',
        ],
        'warehouse': [
            r'warehous',
            r'storage',
            r'fulfillment',
            r'distribution\s*center',
        ],
        '3pl': [
            r'3pl',
            r'third.party\s*logistics',
            r'contract\s*logistics',
        ],
    }
    
    # Country indicators
    COUNTRY_PATTERNS = {
        'VN': [r'vietnam', r'việt\s*nam', r'\.vn\b', r'ho\s*chi\s*minh', r'hanoi'],
        'TH': [r'thailand', r'ไทย', r'\.th\b', r'bangkok'],
        'CN': [r'china', r'中国', r'\.cn\b', r'shanghai', r'beijing'],
        'ID': [r'indonesia', r'\.id\b', r'jakarta'],
        'MY': [r'malaysia', r'\.my\b', r'kuala\s*lumpur'],
        'SG': [r'singapore', r'\.sg\b'],
        'PH': [r'philippines', r'\.ph\b', r'manila'],
    }
    
    # Language detection (simple keyword-based)
    LANGUAGE_INDICATORS = {
        'vi': ['việt', 'và', 'của', 'để', 'trong'],
        'th': ['และ', 'ของ', 'ที่', 'ใน', 'เป็น'],
        'zh': ['的', '是', '在', '了', '和'],
        'id': ['dan', 'yang', 'untuk', 'dengan', 'ini'],
    }
    
    def classify(
        self,
        html_content: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> ClassificationResult:
        """
        Classify a page from its HTML content.
        
        Args:
            html_content: Raw HTML string
            url: Page URL (for domain analysis)
            headers: Optional HTTP headers
            
        Returns:
            ClassificationResult with signals and classifications
        """
        result = ClassificationResult()
        
        if not html_content:
            return result
        
        # Lowercase for pattern matching
        content_lower = html_content.lower()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Detect page type
        page_type, page_confidence = self._detect_page_type(content_lower, url)
        result.page_type = page_type
        result.page_type_confidence = page_confidence
        
        # Detect entity type
        entity_type, entity_confidence = self._detect_entity_type(content_lower)
        result.entity_type = entity_type
        result.entity_type_confidence = entity_confidence
        
        # Detect countries
        result.country_codes = self._detect_countries(content_lower, url)
        
        # Detect languages
        result.detected_languages = self._detect_languages(html_content)
        
        # Detect structure signals
        result.has_contact_page = self._has_link_pattern(content_lower, r'contact|kontakt|liên\s*hệ')
        result.has_about_page = self._has_link_pattern(content_lower, r'about|über|giới\s*thiệu')
        result.has_member_list = self._has_link_pattern(content_lower, r'member|thành\s*viên|会员')
        result.has_pagination = bool(re.search(r'page=\d|/page/\d|class=["\'][^"\']*pagination', content_lower))
        
        # Find sitemaps and feeds
        result.sitemap_urls = self._find_sitemaps(html_content, url)
        result.feed_urls = self._find_feeds(html_content, url)
        result.has_sitemap = len(result.sitemap_urls) > 0
        result.has_rss_feed = len(result.feed_urls) > 0
        
        # Count links
        result.link_count = len(re.findall(r'<a\s+[^>]*href=', content_lower))
        result.external_link_count = self._count_external_links(html_content, domain)
        result.form_count = len(re.findall(r'<form\s', content_lower))
        
        # Find list pages (category/listing pages)
        result.list_page_urls = self._find_list_pages(html_content, url)
        
        # Store raw signals
        result.signals = {
            'domain': domain,
            'path_depth': len([p for p in parsed_url.path.split('/') if p]),
            'has_search': bool(re.search(r'<input[^>]*(?:type=["\']search|name=["\'](?:q|query|search))', content_lower)),
            'title': self._extract_title(html_content),
        }
        
        return result
    
    def _detect_page_type(
        self,
        content: str,
        url: str,
    ) -> Tuple[str, int]:
        """Detect page type from content patterns."""
        scores = {}
        
        for page_type, patterns in self.PAGE_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, content))
                score += min(matches * 10, 30)  # Cap per pattern
            scores[page_type] = score
        
        # URL-based boosts
        url_lower = url.lower()
        if '/members' in url_lower or '/directory' in url_lower:
            scores['directory'] = scores.get('directory', 0) + 20
        if '.gov.' in url_lower or '/gov/' in url_lower:
            scores['gov_registry'] = scores.get('gov_registry', 0) + 30
        
        # Find best match
        if not scores or max(scores.values()) < 10:
            return 'unknown', 30
        
        best_type = max(scores, key=scores.get)
        confidence = min(30 + scores[best_type], 95)
        
        return best_type, confidence
    
    def _detect_entity_type(self, content: str) -> Tuple[str, int]:
        """Detect entity type from content."""
        scores = {}
        
        for entity_type, patterns in self.ENTITY_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, content))
                score += min(matches * 5, 25)
            scores[entity_type] = score
        
        if not scores or max(scores.values()) < 5:
            return 'unknown', 30
        
        best_type = max(scores, key=scores.get)
        confidence = min(30 + scores[best_type] * 2, 90)
        
        return best_type, confidence
    
    def _detect_countries(self, content: str, url: str) -> List[str]:
        """Detect country codes from content and URL."""
        detected = set()
        
        for code, patterns in self.COUNTRY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.add(code)
                    break
                if re.search(pattern, url, re.IGNORECASE):
                    detected.add(code)
                    break
        
        return list(detected)
    
    def _detect_languages(self, content: str) -> List[str]:
        """Detect languages from content."""
        detected = ['en']  # Assume English by default
        
        for lang, indicators in self.LANGUAGE_INDICATORS.items():
            for indicator in indicators:
                if indicator in content:
                    if lang not in detected:
                        detected.append(lang)
                    break
        
        return detected
    
    def _has_link_pattern(self, content: str, pattern: str) -> bool:
        """Check if content has link matching pattern."""
        link_pattern = rf'<a\s+[^>]*href=["\'][^"\']*[^"\']*["\'][^>]*>[^<]*(?:{pattern})[^<]*</a>'
        return bool(re.search(link_pattern, content, re.IGNORECASE))
    
    def _find_sitemaps(self, content: str, base_url: str) -> List[str]:
        """Find sitemap URLs in content."""
        sitemaps = []
        
        # Look in <link> tags
        link_pattern = r'<link[^>]*href=["\']([^"\']*sitemap[^"\']*)["\']'
        for match in re.finditer(link_pattern, content, re.IGNORECASE):
            url = match.group(1)
            if not url.startswith('http'):
                url = urljoin(base_url, url)
            sitemaps.append(url)
        
        # Common sitemap locations
        parsed = urlparse(base_url)
        common = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
        ]
        for url in common:
            if url not in sitemaps:
                sitemaps.append(url)
        
        return sitemaps[:5]
    
    def _find_feeds(self, content: str, base_url: str) -> List[str]:
        """Find RSS/Atom feed URLs in content."""
        feeds = []
        
        # Look for feed links
        patterns = [
            r'<link[^>]*type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']',
            r'<a[^>]*href=["\']([^"\']*(?:rss|feed|atom)[^"\']*)["\']',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                url = match.group(1)
                if not url.startswith('http'):
                    url = urljoin(base_url, url)
                if url not in feeds:
                    feeds.append(url)
        
        return feeds[:5]
    
    def _find_list_pages(self, content: str, base_url: str) -> List[str]:
        """Find category/listing page URLs."""
        list_pages = []
        
        patterns = [
            r'<a[^>]*href=["\']([^"\']*(?:categor|list|companies|members|directory)[^"\']*)["\']',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                url = match.group(1)
                if url.startswith('#') or url.startswith('javascript:'):
                    continue
                if not url.startswith('http'):
                    url = urljoin(base_url, url)
                if url not in list_pages:
                    list_pages.append(url)
        
        return list_pages[:10]
    
    def _count_external_links(self, content: str, domain: str) -> int:
        """Count links pointing to external domains."""
        count = 0
        for match in re.finditer(r'href=["\']https?://([^/"\'\s]+)', content, re.IGNORECASE):
            link_domain = match.group(1).lower()
            if domain.lower() not in link_domain:
                count += 1
        return count
    
    def _extract_title(self, content: str) -> str:
        """Extract page title."""
        match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]
        return ''
