"""
Base crawler class for EMCIP.
All crawler implementations should inherit from this.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base class for all crawlers.
    """

    def __init__(self, source):
        """
        Initialize crawler with a source.

        Args:
            source: Source model instance
        """
        self.source = source
        self.config = source.crawler_config or {}
        self.max_pages = self.config.get('max_pages', 3)
        self.delay = self.config.get('delay', 2)  # seconds between requests
        self.user_agent = self.config.get(
            'user_agent',
            'EMCIP-Bot/1.0 (Content Intelligence Platform)'
        )

    @abstractmethod
    def crawl(self):
        """
        Main crawl method. Must be implemented by subclasses.

        Returns:
            dict with crawl results:
            {
                'total_found': int,
                'new_articles': int,
                'duplicates': int,
                'errors': int,
                'article_ids': list of UUIDs
            }
        """
        pass

    def _is_duplicate(self, url):
        """
        Check if an article with this URL already exists.

        Args:
            url: Article URL

        Returns:
            bool: True if duplicate exists
        """
        from apps.articles.models import Article
        return Article.objects.filter(url=url).exists()

    def _save_article(self, url, title, html, metadata=None):
        """
        Save a crawled article to the database.

        Args:
            url: Article URL
            title: Article title
            html: Raw HTML content
            metadata: Optional dict of additional metadata

        Returns:
            Article instance or None if duplicate/error
        """
        # Check for duplicates
        if self._is_duplicate(url):
            logger.debug(f"Duplicate article: {url}")
            return None

        try:
            from apps.articles.models import Article

            # Extract basic metadata
            metadata = metadata or {}
            author = metadata.get('author', '')
            published_date = metadata.get('published_date')

            # Create article
            article = Article.objects.create(
                source=self.source,
                url=url,
                title=title,
                author=author,
                published_date=published_date,
                raw_html=html,
                processing_status='collected',
                metadata=metadata
            )

            logger.info(f"Saved article: {title} ({url})")
            return article

        except Exception as e:
            logger.error(f"Error saving article {url}: {e}")
            return None

    def _extract_metadata(self, response):
        """
        Extract basic metadata from a response.
        Can be overridden by subclasses for specific extraction logic.

        Args:
            response: Response object (varies by crawler type)

        Returns:
            dict with metadata
        """
        return {
            'crawled_at': timezone.now().isoformat(),
            'status_code': getattr(response, 'status', None),
        }

    def _should_crawl_url(self, url):
        """
        Check if a URL should be crawled based on source configuration.

        Args:
            url: URL to check

        Returns:
            bool: True if URL should be crawled
        """
        # Basic filtering - can be extended
        if not url or not url.startswith('http'):
            return False

        # Check if URL is from the same domain
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.netloc != self.source.domain:
            return False

        return True

    def _update_source_stats(self, results):
        """
        Update source statistics after crawling.

        Args:
            results: Crawl results dict
        """
        try:
            self.source.total_articles_collected += results.get('new_articles', 0)
            self.source.last_crawled_at = timezone.now()

            if results.get('errors', 0) == 0:
                self.source.last_successful_crawl = timezone.now()
                self.source.crawl_errors_count = 0
                self.source.last_error_message = ''
            else:
                self.source.crawl_errors_count += 1

            self.source.save()
            logger.info(f"Updated source stats for {self.source.name}")

        except Exception as e:
            logger.error(f"Error updating source stats: {e}")
