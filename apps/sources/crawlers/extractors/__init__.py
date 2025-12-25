"""
Extractors package.

Provides different strategies for extracting:
- Links from HTML content (for crawling)
- Article content from HTML (for processing)
"""

from .bs4_link_extractor import BS4LinkExtractor
from .content_extractor import (
    ContentExtractor,
    TrafilaturaExtractor,
    Newspaper3kExtractor,
    HybridContentExtractor,
    ExtractionResult,
    ExtractionQuality,
    extract_content,
    TRAFILATURA_AVAILABLE,
    NEWSPAPER_AVAILABLE,
)

__all__ = [
    # Link extractors
    'BS4LinkExtractor',
    
    # Content extractors
    'ContentExtractor',
    'TrafilaturaExtractor',
    'Newspaper3kExtractor', 
    'HybridContentExtractor',
    'ExtractionResult',
    'ExtractionQuality',
    'extract_content',
    'TRAFILATURA_AVAILABLE',
    'NEWSPAPER_AVAILABLE',
]
