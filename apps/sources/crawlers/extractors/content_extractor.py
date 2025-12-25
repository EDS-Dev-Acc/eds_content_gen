"""
Content extractors for article body extraction.

Provides multiple strategies for extracting clean article text from HTML:
- TrafilaturaExtractor: Uses trafilatura library (best for news articles)
- Newspaper3kExtractor: Uses newspaper3k library (good fallback)
- HybridContentExtractor: Combines multiple strategies for best results
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)

# Check for trafilatura
try:
    import trafilatura
    from trafilatura import extract
    from trafilatura.metadata import extract_metadata
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not installed. Install with: pip install trafilatura")

# Check for newspaper3k
try:
    from newspaper import Article as NewsArticle
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    logger.warning("newspaper3k not installed. Install with: pip install newspaper3k")


class ExtractionQuality(Enum):
    """Quality rating for extraction results."""
    EXCELLENT = 'excellent'  # >1000 words, well-structured
    GOOD = 'good'           # 500-1000 words
    FAIR = 'fair'           # 200-500 words
    POOR = 'poor'           # <200 words or issues detected
    FAILED = 'failed'       # Extraction failed


@dataclass
class ExtractionResult:
    """Result of content extraction."""
    text: str = ''
    title: str = ''
    author: str = ''
    authors: List[str] = field(default_factory=list)
    published_date: Optional[datetime] = None
    language: str = ''
    description: str = ''
    
    # Metadata
    word_count: int = 0
    paragraph_count: int = 0
    images_count: int = 0
    has_paywall: bool = False
    
    # Quality metrics
    quality: ExtractionQuality = ExtractionQuality.FAILED
    extractor_used: str = ''
    extraction_time_ms: int = 0
    confidence_score: float = 0.0
    
    # Raw data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return bool(self.text) and self.quality != ExtractionQuality.FAILED
    
    def __post_init__(self):
        if self.text:
            self.word_count = len(self.text.split())
            self.paragraph_count = len([p for p in self.text.split('\n\n') if p.strip()])
            self._assess_quality()
    
    def _assess_quality(self):
        """Assess extraction quality based on content."""
        if not self.text:
            self.quality = ExtractionQuality.FAILED
            self.confidence_score = 0.0
            return
        
        # Word count assessment
        if self.word_count >= 1000:
            self.quality = ExtractionQuality.EXCELLENT
            base_score = 0.9
        elif self.word_count >= 500:
            self.quality = ExtractionQuality.GOOD
            base_score = 0.75
        elif self.word_count >= 200:
            self.quality = ExtractionQuality.FAIR
            base_score = 0.5
        else:
            self.quality = ExtractionQuality.POOR
            base_score = 0.3
        
        # Adjust for metadata availability
        if self.title:
            base_score += 0.02
        if self.author or self.authors:
            base_score += 0.02
        if self.published_date:
            base_score += 0.02
        if self.language:
            base_score += 0.01
        
        # Penalize for quality issues
        text_lower = self.text.lower()
        if 'subscribe' in text_lower and 'newsletter' in text_lower:
            base_score -= 0.05  # Possible boilerplate
        if self.has_paywall:
            base_score -= 0.1
        
        self.confidence_score = min(1.0, max(0.0, base_score))


class ContentExtractor(ABC):
    """Abstract base class for content extractors."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this extractor."""
        pass
    
    @abstractmethod
    def extract(self, html: str, url: str = '') -> ExtractionResult:
        """
        Extract article content from HTML.
        
        Args:
            html: Raw HTML content
            url: Source URL (helps with metadata extraction)
            
        Returns:
            ExtractionResult with extracted content
        """
        pass
    
    def is_available(self) -> bool:
        """Check if this extractor's dependencies are available."""
        return True


class TrafilaturaExtractor(ContentExtractor):
    """
    Content extractor using trafilatura library.
    
    Trafilatura is excellent for:
    - News articles
    - Blog posts
    - Web articles in general
    - Handling complex page layouts
    - Extracting metadata
    """
    
    def __init__(
        self,
        include_comments: bool = False,
        include_tables: bool = True,
        include_links: bool = False,
        include_images: bool = False,
        favor_precision: bool = True,
        favor_recall: bool = False,
        deduplicate: bool = True,
    ):
        """
        Initialize TrafilaturaExtractor.
        
        Args:
            include_comments: Include comment sections
            include_tables: Include table content
            include_links: Include hyperlinks in output
            include_images: Include image descriptions
            favor_precision: Prefer precision over recall (fewer false positives)
            favor_recall: Prefer recall over precision (fewer missed content)
            deduplicate: Remove duplicate paragraphs
        """
        self.include_comments = include_comments
        self.include_tables = include_tables
        self.include_links = include_links
        self.include_images = include_images
        self.favor_precision = favor_precision
        self.favor_recall = favor_recall
        self.deduplicate = deduplicate
    
    @property
    def name(self) -> str:
        return 'trafilatura'
    
    def is_available(self) -> bool:
        return TRAFILATURA_AVAILABLE
    
    def extract(self, html: str, url: str = '') -> ExtractionResult:
        """Extract content using trafilatura."""
        import time
        start = time.time()
        
        if not TRAFILATURA_AVAILABLE:
            return ExtractionResult(
                extractor_used=self.name,
                metadata={'error': 'trafilatura not installed'}
            )
        
        if not html:
            return ExtractionResult(
                extractor_used=self.name,
                metadata={'error': 'No HTML provided'}
            )
        
        try:
            # Extract main content
            text = extract(
                html,
                url=url,
                include_comments=self.include_comments,
                include_tables=self.include_tables,
                include_links=self.include_links,
                include_images=self.include_images,
                favor_precision=self.favor_precision,
                favor_recall=self.favor_recall,
                deduplicate=self.deduplicate,
                output_format='txt',
            )
            
            # Extract metadata separately (trafilatura 2.0+ uses default_url)
            metadata_obj = extract_metadata(html, default_url=url)
            
            elapsed_ms = int((time.time() - start) * 1000)
            
            if not text:
                return ExtractionResult(
                    extractor_used=self.name,
                    extraction_time_ms=elapsed_ms,
                    metadata={'error': 'No content extracted'}
                )
            
            # Build result
            result = ExtractionResult(
                text=text.strip(),
                title=metadata_obj.title if metadata_obj else '',
                author=metadata_obj.author if metadata_obj else '',
                published_date=self._parse_date(metadata_obj.date if metadata_obj else None),
                language=metadata_obj.language if metadata_obj else '',
                description=metadata_obj.description if metadata_obj else '',
                extractor_used=self.name,
                extraction_time_ms=elapsed_ms,
                metadata={
                    'sitename': metadata_obj.sitename if metadata_obj else None,
                    'categories': metadata_obj.categories if metadata_obj else [],
                    'tags': metadata_obj.tags if metadata_obj else [],
                    'license': metadata_obj.license if metadata_obj else None,
                }
            )
            
            # Check for paywall indicators
            result.has_paywall = self._detect_paywall(html, text)
            
            return result
            
        except Exception as e:
            logger.error(f"Trafilatura extraction failed: {e}")
            return ExtractionResult(
                extractor_used=self.name,
                extraction_time_ms=int((time.time() - start) * 1000),
                metadata={'error': str(e)}
            )
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except Exception:
            return None
    
    def _detect_paywall(self, html: str, extracted_text: str) -> bool:
        """Detect if article is behind a paywall."""
        html_lower = html.lower()
        
        paywall_indicators = [
            'paywall',
            'subscribe to read',
            'subscribers only',
            'premium content',
            'sign up to continue reading',
            'create a free account',
            'subscription required',
        ]
        
        for indicator in paywall_indicators:
            if indicator in html_lower:
                # Check if extracted text is suspiciously short
                if len(extracted_text.split()) < 300:
                    return True
        
        return False


class Newspaper3kExtractor(ContentExtractor):
    """
    Content extractor using newspaper3k library.
    
    Good as a fallback extractor with different parsing approach.
    """
    
    def __init__(self, language: str = 'en'):
        self.language = language
    
    @property
    def name(self) -> str:
        return 'newspaper3k'
    
    def is_available(self) -> bool:
        return NEWSPAPER_AVAILABLE
    
    def extract(self, html: str, url: str = '') -> ExtractionResult:
        """Extract content using newspaper3k."""
        import time
        start = time.time()
        
        if not NEWSPAPER_AVAILABLE:
            return ExtractionResult(
                extractor_used=self.name,
                metadata={'error': 'newspaper3k not installed'}
            )
        
        if not html:
            return ExtractionResult(
                extractor_used=self.name,
                metadata={'error': 'No HTML provided'}
            )
        
        try:
            article = NewsArticle(url=url or 'http://example.com', language=self.language)
            article.download(input_html=html)
            article.parse()
            
            elapsed_ms = int((time.time() - start) * 1000)
            
            text = article.text.strip() if article.text else ''
            
            if not text:
                return ExtractionResult(
                    extractor_used=self.name,
                    extraction_time_ms=elapsed_ms,
                    metadata={'error': 'No content extracted'}
                )
            
            return ExtractionResult(
                text=text,
                title=article.title or '',
                authors=article.authors or [],
                published_date=article.publish_date,
                language=article.meta_lang or '',
                description=article.meta_description or '',
                images_count=len(article.images) if article.images else 0,
                extractor_used=self.name,
                extraction_time_ms=elapsed_ms,
                metadata={
                    'keywords': article.keywords or [],
                    'movies': article.movies or [],
                }
            )
            
        except Exception as e:
            logger.error(f"Newspaper3k extraction failed: {e}")
            return ExtractionResult(
                extractor_used=self.name,
                extraction_time_ms=int((time.time() - start) * 1000),
                metadata={'error': str(e)}
            )


class HybridContentExtractor(ContentExtractor):
    """
    Hybrid extractor that uses multiple strategies for best results.
    
    Strategy:
    1. Try trafilatura first (best for news/articles)
    2. If poor result, try newspaper3k
    3. Compare results and pick best
    4. Optionally merge metadata from both
    """
    
    def __init__(
        self,
        primary: Optional[ContentExtractor] = None,
        fallback: Optional[ContentExtractor] = None,
        min_quality: ExtractionQuality = ExtractionQuality.FAIR,
        merge_metadata: bool = True,
    ):
        """
        Initialize HybridContentExtractor.
        
        Args:
            primary: Primary extractor (default: TrafilaturaExtractor)
            fallback: Fallback extractor (default: Newspaper3kExtractor)
            min_quality: Minimum quality to accept from primary before trying fallback
            merge_metadata: Whether to merge metadata from both extractors
        """
        self.primary = primary
        self.fallback = fallback
        self.min_quality = min_quality
        self.merge_metadata = merge_metadata
        
        # Initialize extractors lazily
        self._primary_initialized = False
        self._fallback_initialized = False
    
    def _ensure_extractors(self):
        """Initialize extractors if needed."""
        if not self._primary_initialized:
            if self.primary is None and TRAFILATURA_AVAILABLE:
                self.primary = TrafilaturaExtractor()
            self._primary_initialized = True
        
        if not self._fallback_initialized:
            if self.fallback is None and NEWSPAPER_AVAILABLE:
                self.fallback = Newspaper3kExtractor()
            self._fallback_initialized = True
    
    @property
    def name(self) -> str:
        return 'hybrid'
    
    def is_available(self) -> bool:
        self._ensure_extractors()
        return (self.primary and self.primary.is_available()) or \
               (self.fallback and self.fallback.is_available())
    
    def extract(self, html: str, url: str = '') -> ExtractionResult:
        """Extract using hybrid strategy."""
        import time
        start = time.time()
        
        self._ensure_extractors()
        
        if not self.is_available():
            return ExtractionResult(
                extractor_used=self.name,
                metadata={'error': 'No extractors available'}
            )
        
        primary_result = None
        fallback_result = None
        
        # Try primary extractor
        if self.primary and self.primary.is_available():
            primary_result = self.primary.extract(html, url)
            logger.debug(
                f"Primary ({self.primary.name}) result: "
                f"{primary_result.word_count} words, quality={primary_result.quality.value}"
            )
            
            # Check if good enough
            if self._quality_meets_threshold(primary_result.quality):
                primary_result.metadata['hybrid_strategy'] = 'primary_only'
                return primary_result
        
        # Try fallback extractor
        if self.fallback and self.fallback.is_available():
            fallback_result = self.fallback.extract(html, url)
            logger.debug(
                f"Fallback ({self.fallback.name}) result: "
                f"{fallback_result.word_count} words, quality={fallback_result.quality.value}"
            )
        
        # Compare and pick best
        best_result = self._pick_best(primary_result, fallback_result)
        
        # Optionally merge metadata
        if self.merge_metadata and primary_result and fallback_result:
            best_result = self._merge_results(best_result, primary_result, fallback_result)
        
        best_result.extraction_time_ms = int((time.time() - start) * 1000)
        
        return best_result
    
    def _quality_meets_threshold(self, quality: ExtractionQuality) -> bool:
        """Check if quality meets minimum threshold."""
        quality_order = [
            ExtractionQuality.FAILED,
            ExtractionQuality.POOR,
            ExtractionQuality.FAIR,
            ExtractionQuality.GOOD,
            ExtractionQuality.EXCELLENT,
        ]
        return quality_order.index(quality) >= quality_order.index(self.min_quality)
    
    def _pick_best(
        self,
        primary: Optional[ExtractionResult],
        fallback: Optional[ExtractionResult]
    ) -> ExtractionResult:
        """Pick the best result from primary and fallback."""
        if not primary and not fallback:
            return ExtractionResult(extractor_used=self.name)
        
        if not primary or not primary.success:
            if fallback and fallback.success:
                fallback.metadata['hybrid_strategy'] = 'fallback_only'
                return fallback
            return primary or fallback or ExtractionResult(extractor_used=self.name)
        
        if not fallback or not fallback.success:
            primary.metadata['hybrid_strategy'] = 'primary_only'
            return primary
        
        # Both succeeded - compare
        if primary.confidence_score >= fallback.confidence_score:
            primary.metadata['hybrid_strategy'] = 'primary_preferred'
            return primary
        else:
            fallback.metadata['hybrid_strategy'] = 'fallback_preferred'
            return fallback
    
    def _merge_results(
        self,
        best: ExtractionResult,
        primary: ExtractionResult,
        fallback: ExtractionResult
    ) -> ExtractionResult:
        """Merge metadata from both results into the best one."""
        # Use best title (prefer non-empty)
        if not best.title:
            best.title = primary.title or fallback.title
        
        # Use best author info
        if not best.author and not best.authors:
            best.author = primary.author or fallback.author
            best.authors = primary.authors or fallback.authors
        
        # Use best published date
        if not best.published_date:
            best.published_date = primary.published_date or fallback.published_date
        
        # Use best language
        if not best.language:
            best.language = primary.language or fallback.language
        
        # Use best description
        if not best.description:
            best.description = primary.description or fallback.description
        
        # Merge metadata dicts
        merged_meta = {
            **fallback.metadata,
            **primary.metadata,
            **best.metadata,
            'primary_extractor': primary.extractor_used,
            'fallback_extractor': fallback.extractor_used,
            'primary_word_count': primary.word_count,
            'fallback_word_count': fallback.word_count,
        }
        best.metadata = merged_meta
        best.extractor_used = self.name
        
        return best


# Convenience function
def extract_content(html: str, url: str = '', strategy: str = 'hybrid') -> ExtractionResult:
    """
    Extract article content from HTML.
    
    Args:
        html: Raw HTML content
        url: Source URL
        strategy: Extraction strategy ('hybrid', 'trafilatura', 'newspaper3k')
        
    Returns:
        ExtractionResult with extracted content
    """
    if strategy == 'trafilatura':
        extractor = TrafilaturaExtractor()
    elif strategy == 'newspaper3k':
        extractor = Newspaper3kExtractor()
    else:
        extractor = HybridContentExtractor()
    
    return extractor.extract(html, url)
