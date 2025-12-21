"""
Simple HTTP crawler for EMCIP.
Uses requests library for now (will use Scrapy in future with full dependencies).
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import logging
from .base import BaseCrawler

logger = logging.getLogger(__name__)


class ScrapyCrawler(BaseCrawler):
    """
    Simple HTTP-based crawler using requests and BeautifulSoup.
    Will be replaced with full Scrapy implementation when dependencies are installed.
    """

    def crawl(self):
        """
        Crawl the source and collect articles.

        Returns:
            dict with crawl results
        """
        results = {
            'total_found': 0,
            'new_articles': 0,
            'duplicates': 0,
            'errors': 0,
            'article_ids': []
        }

        try:
            logger.info(f"Starting crawl of {self.source.name} ({self.source.url})")

            # Fetch the main page
            response = self._fetch_page(self.source.url)
            if not response:
                results['errors'] += 1
                self._update_source_stats(results)
                return results

            # Extract article links
            article_links = self._extract_article_links(response)
            results['total_found'] = len(article_links)

            logger.info(f"Found {len(article_links)} potential articles")

            # Process each article (up to max configured)
            max_articles = self.config.get('max_articles', 50)
            for i, link in enumerate(article_links[:max_articles]):
                if i > 0:
                    time.sleep(self.delay)  # Respect rate limiting

                article = self._process_article(link)
                if article:
                    results['new_articles'] += 1
                    results['article_ids'].append(str(article.id))
                else:
                    # Could be duplicate or error
                    if self._is_duplicate(link):
                        results['duplicates'] += 1

            logger.info(
                f"Crawl complete: {results['new_articles']} new, "
                f"{results['duplicates']} duplicates"
            )

        except Exception as e:
            logger.error(f"Error during crawl: {e}")
            results['errors'] += 1
            self.source.last_error_message = str(e)
            self.source.save()

        finally:
            self._update_source_stats(results)

        return results

    def _fetch_page(self, url):
        """
        Fetch a page with proper headers and error handling.

        Args:
            url: URL to fetch

        Returns:
            Response object or None if error
        """
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            # Add custom headers from source config
            if self.source.custom_headers:
                headers.update(self.source.custom_headers)

            response = requests.get(
                url,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )

            response.raise_for_status()
            return response

        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _extract_article_links(self, response):
        """
        Extract article links from the response.
        Uses simple heuristics to identify article URLs.

        Args:
            response: Response object

        Returns:
            list of article URLs
        """
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []

            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']

                # Convert relative URLs to absolute
                full_url = urljoin(response.url, href)

                # Filter for article-like URLs
                if self._looks_like_article(full_url):
                    if full_url not in links:
                        links.append(full_url)

            return links

        except Exception as e:
            logger.error(f"Error extracting links: {e}")
            return []

    def _looks_like_article(self, url):
        """
        Heuristic to determine if a URL looks like an article.

        Args:
            url: URL to check

        Returns:
            bool: True if URL looks like an article
        """
        # Basic checks
        if not self._should_crawl_url(url):
            return False

        # Exclude common non-article paths
        exclude_patterns = [
            '/category/', '/tag/', '/author/', '/page/',
            '/search/', '/archive/', '/about', '/contact',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js'
        ]

        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Include patterns (common article URL patterns)
        include_patterns = [
            '/article/', '/post/', '/news/', '/blog/',
            '/story/', '/analysis/', '/report/'
        ]

        # If URL contains include patterns, it's likely an article
        for pattern in include_patterns:
            if pattern in url_lower:
                return True

        # If URL has a path with multiple segments, might be an article
        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split('/') if s]
        if len(path_segments) >= 2:
            return True

        return False

    def _process_article(self, url):
        """
        Fetch and process a single article.

        Args:
            url: Article URL

        Returns:
            Article instance or None
        """
        try:
            # Check if duplicate first (before fetching)
            if self._is_duplicate(url):
                return None

            # Fetch article page
            response = self._fetch_page(url)
            if not response:
                return None

            # Extract article data
            article_data = self._extract_article_data(response)
            if not article_data:
                return None

            # Save article
            article = self._save_article(
                url=url,
                title=article_data['title'],
                html=response.text,
                metadata=article_data.get('metadata', {})
            )

            return article

        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")
            return None

    def _extract_article_data(self, response):
        """
        Extract article data from response.

        Args:
            response: Response object

        Returns:
            dict with article data or None
        """
        try:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Try to find title
            title = None

            # Try meta tags first
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content']

            # Try h1 tag
            if not title:
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)

            # Try title tag
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)

            if not title:
                logger.warning(f"No title found for {response.url}")
                return None

            # Extract metadata
            metadata = {
                'url': response.url,
                'status_code': response.status_code,
            }

            # Try to extract author
            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta and author_meta.get('content'):
                metadata['author'] = author_meta['content']

            # Try to extract published date
            date_meta = soup.find('meta', property='article:published_time')
            if date_meta and date_meta.get('content'):
                metadata['published_date_str'] = date_meta['content']

            return {
                'title': title,
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"Error extracting article data: {e}")
            return None
