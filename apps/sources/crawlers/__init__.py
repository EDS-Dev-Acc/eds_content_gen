"""
Crawler package for EMCIP.
Provides various crawler implementations for different source types.
"""

from .base import BaseCrawler
from .scrapy_crawler import ScrapyCrawler


def get_crawler(source):
    """
    Factory function to get the appropriate crawler for a source.

    Args:
        source: Source model instance

    Returns:
        Appropriate crawler instance
    """
    crawler_type = source.crawler_type.lower()

    if crawler_type == 'scrapy':
        return ScrapyCrawler(source)
    elif crawler_type == 'playwright':
        # TODO: Implement in future session
        raise NotImplementedError("Playwright crawler not yet implemented")
    elif crawler_type == 'selenium':
        # TODO: Implement in future session
        raise NotImplementedError("Selenium crawler not yet implemented")
    else:
        # Default to Scrapy
        return ScrapyCrawler(source)


__all__ = ['BaseCrawler', 'ScrapyCrawler', 'get_crawler']
