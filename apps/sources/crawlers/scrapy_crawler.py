"""
Simple HTTP crawler for EMCIP.
Uses requests library for now (will use Scrapy in future with full dependencies).
Supports pagination via URL parameters, path-based pagination, and next-link following.
Features per-domain rate limiting, URL normalization, and optional async fetching.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, urlunparse
import time
import logging
from .base import BaseCrawler
from .registry import get_rules_for_domain, get_pagination_config
from .utils import (
    URLNormalizer,
    URLDeduplicator,
    DomainRateLimiter,
    fetch_urls_parallel,
    normalize_url,
)

logger = logging.getLogger(__name__)


class ScrapyCrawler(BaseCrawler):
    """
    Simple HTTP-based crawler using requests and BeautifulSoup.
    Supports pagination to collect articles from multiple pages.
    Features per-domain rate limiting, URL normalization, and async article fetching.
    Will be replaced with full Scrapy implementation when dependencies are installed.
    """

    def __init__(self, source, config: dict = None):
        super().__init__(source, config=config)
        self.rules = get_rules_for_domain(source.domain)
        self.pagination_config = get_pagination_config(source.domain)
        
        # Initialize URL normalizer and deduplicator
        self.url_normalizer = URLNormalizer(
            remove_trailing_slash=True,
            remove_fragments=True,
            remove_tracking_params=True,
        )
        self.url_deduplicator = URLDeduplicator(self.url_normalizer)
        
        # Initialize per-domain rate limiter
        domain_delays = self.config.get('domain_delays', {})
        self.rate_limiter = DomainRateLimiter(
            default_delay=self.delay,
            domain_delays=domain_delays,
        )
        
        # Async fetching configuration
        self.use_async_fetch = self.config.get('use_async_fetch', True)
        self.max_concurrent = self.config.get('max_concurrent', 5)

    def crawl(self):
        """
        Crawl the source and collect articles with pagination support.

        Returns:
            dict with crawl results
        """
        results = {
            'total_found': 0,
            'new_articles': 0,
            'duplicates': 0,
            'errors': 0,
            'article_ids': [],
            'pages_crawled': 0
        }

        try:
            logger.info(f"Starting crawl of {self.source.name} ({self.source.url})")

            # Collect article links from all pages
            all_article_links = self._crawl_with_pagination()
            results['total_found'] = len(all_article_links)
            results['pages_crawled'] = getattr(self, '_pages_crawled', 1)

            logger.info(f"Found {len(all_article_links)} potential articles across {results['pages_crawled']} pages")

            # Process each article (up to max configured)
            max_articles = self.config.get('max_articles', 50)
            articles_to_process = all_article_links[:max_articles]
            
            # Use async fetching if enabled and aiohttp is available
            if self.use_async_fetch and len(articles_to_process) > 1:
                results = self._process_articles_async(articles_to_process, results)
            else:
                results = self._process_articles_sync(articles_to_process, results)

            logger.info(
                f"Crawl complete: {results['new_articles']} new, "
                f"{results['duplicates']} duplicates from {results['pages_crawled']} pages"
            )

        except Exception as e:
            logger.error(f"Error during crawl: {e}")
            results['errors'] += 1
            self.source.last_error_message = str(e)
            self.source.save()

        finally:
            self._update_source_stats(results)

        return results

    def _process_articles_sync(self, urls, results):
        """
        Process articles sequentially with rate limiting.
        
        Args:
            urls: List of article URLs to process
            results: Results dict to update
            
        Returns:
            Updated results dict
        """
        for i, url in enumerate(urls):
            if i > 0:
                # Use per-domain rate limiter instead of fixed delay
                domain = urlparse(url).netloc
                self.rate_limiter.wait_if_needed(domain)

            article = self._process_article(url)
            if article:
                results['new_articles'] += 1
                results['article_ids'].append(str(article.id))
            else:
                # Could be duplicate or error
                if self._is_duplicate(url):
                    results['duplicates'] += 1
        
        return results

    def _process_articles_async(self, urls, results):
        """
        Process articles in parallel using async fetching.
        
        Args:
            urls: List of article URLs to process
            results: Results dict to update
            
        Returns:
            Updated results dict
        """
        # Filter out duplicates before fetching
        urls_to_fetch = []
        for url in urls:
            normalized = self.url_normalizer.normalize(url)
            if not self._is_duplicate(normalized):
                urls_to_fetch.append(url)
            else:
                results['duplicates'] += 1
        
        if not urls_to_fetch:
            return results
        
        logger.info(f"Async fetching {len(urls_to_fetch)} articles (max concurrent: {self.max_concurrent})")
        
        # Build headers
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        if self.source.custom_headers:
            headers.update(self.source.custom_headers)
        
        # Fetch all URLs in parallel
        try:
            fetch_results = fetch_urls_parallel(
                urls_to_fetch,
                headers=headers,
                max_concurrent=self.max_concurrent,
                timeout=30,
                rate_limiter=self.rate_limiter,
            )
        except Exception as e:
            logger.warning(f"Async fetch failed, falling back to sync: {e}")
            return self._process_articles_sync(urls_to_fetch, results)
        
        # Process fetched content
        for url, html, status_code, error in fetch_results:
            if error:
                logger.debug(f"Error fetching {url}: {error}")
                continue
            
            if not html or status_code != 200:
                continue
            
            # Extract and save article
            try:
                article_data = self._extract_article_data_from_html(url, html)
                if article_data:
                    article = self._save_article(
                        url=self.url_normalizer.normalize(url),
                        title=article_data['title'],
                        html=html,
                        metadata=article_data.get('metadata', {})
                    )
                    if article:
                        results['new_articles'] += 1
                        results['article_ids'].append(str(article.id))
            except Exception as e:
                logger.debug(f"Error processing {url}: {e}")
        
        return results

    def _extract_article_data_from_html(self, url, html):
        """
        Extract article data from HTML string.
        
        Args:
            url: Article URL
            html: HTML content string
            
        Returns:
            dict with article data or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
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
                logger.warning(f"No title found for {url}")
                return None
            
            # Extract metadata
            metadata = {
                'url': url,
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
            logger.error(f"Error extracting article data from HTML: {e}")
            return None

    def _crawl_with_pagination(self):
        """
        Crawl multiple pages based on pagination configuration.
        Uses per-domain rate limiting and URL normalization.
        
        Returns:
            list of unique normalized article URLs from all pages
        """
        all_links = []
        current_page = self.pagination_config['start_page']
        self._pages_crawled = 0
        
        pagination_type = self.pagination_config['pagination_type']
        
        # Start with the base URL
        current_url = self.source.url
        
        while self._pages_crawled < self.max_pages:
            # Apply per-domain rate limiting
            if self._pages_crawled > 0:
                self.rate_limiter.wait_if_needed(self.source.domain)
            
            response = self._fetch_page(current_url)
            if not response:
                logger.warning(f"Failed to fetch page {self._pages_crawled + 1}: {current_url}")
                break
            
            self._pages_crawled += 1
            logger.debug(f"Crawling page {self._pages_crawled}: {current_url}")
            
            # Extract article links from this page
            page_links = self._extract_article_links(response)
            
            # Track new links using deduplicator (normalizes URLs automatically)
            new_links_count = 0
            for link in page_links:
                normalized = self.url_deduplicator.add_if_new(link)
                if normalized:
                    all_links.append(normalized)
                    new_links_count += 1
            
            logger.info(f"Page {self._pages_crawled}: found {len(page_links)} links, {new_links_count} new")
            
            # If no new links found, we've likely hit the end of content
            if new_links_count == 0 and self._pages_crawled > 1:
                logger.info("No new links found, stopping pagination")
                break
            
            # Get next page URL based on pagination type
            next_url = self._get_next_page_url(
                current_url, 
                current_page, 
                pagination_type,
                response
            )
            
            if not next_url:
                logger.debug("No next page URL available, stopping pagination")
                break
            
            current_url = next_url
            current_page += self.pagination_config['page_increment']
        
        logger.info(f"Pagination complete: {self._pages_crawled} pages, {len(all_links)} unique articles")
        return all_links

    def _get_next_page_url(self, current_url, current_page, pagination_type, response):
        """
        Generate the next page URL based on pagination configuration.
        
        Args:
            current_url: Current page URL
            current_page: Current page number
            pagination_type: Type of pagination ('param', 'path', 'next_link', 'none')
            response: Response object (for next_link detection)
        
        Returns:
            Next page URL or None if no more pages
        """
        if pagination_type == 'none':
            return None
        
        next_page = current_page + self.pagination_config['page_increment']
        
        if pagination_type == 'param':
            # URL parameter pagination: ?page=2
            return self._build_param_url(current_url, next_page)
        
        elif pagination_type == 'path':
            # Path-based pagination: /page/2/
            return self._build_path_url(current_url, next_page)
        
        elif pagination_type == 'next_link':
            # Follow "next" link on page
            return self._find_next_link(response)
        
        else:
            # Default to parameter-based pagination
            return self._build_param_url(current_url, next_page)

    def _build_param_url(self, base_url, page_number):
        """
        Build URL with page parameter.
        
        Args:
            base_url: Base URL to add parameter to
            page_number: Page number to add
        
        Returns:
            URL with page parameter
        """
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query)
        
        # Update or add page parameter
        page_param = self.pagination_config['page_param']
        query_params[page_param] = [str(page_number)]
        
        # Rebuild URL with updated query string
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        
        return new_url

    def _build_path_url(self, base_url, page_number):
        """
        Build URL with page in path.
        
        Args:
            base_url: Base URL to modify
            page_number: Page number to include in path
        
        Returns:
            URL with page in path
        """
        parsed = urlparse(base_url)
        path_format = self.pagination_config['page_path_format']
        
        # Remove existing pagination from path if present
        path = parsed.path.rstrip('/')
        
        # Check if path already contains pagination pattern
        import re
        pagination_pattern = path_format.replace('{page}', r'\d+')
        path = re.sub(pagination_pattern.rstrip('/'), '', path)
        
        # Add new pagination
        page_path = path_format.format(page=page_number)
        new_path = path + page_path
        
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            new_path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return new_url

    def _find_next_link(self, response):
        """
        Find "next page" link in the response HTML.
        
        Args:
            response: Response object
        
        Returns:
            Next page URL or None
        """
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            selector = self.pagination_config['next_link_selector']
            
            # Try the configured selector
            next_link = soup.select_one(selector)
            
            if next_link and next_link.get('href'):
                href = next_link['href']
                # Convert relative URL to absolute
                next_url = urljoin(response.url, href)
                
                # Verify it's on the same domain
                if urlparse(next_url).netloc == self.source.domain:
                    return next_url
            
            return None
            
        except Exception as e:
            logger.warning(f"Error finding next link: {e}")
            return None

    def _fetch_page(self, url):
        """
        Fetch a page with proper headers, SSRF protection, and error handling.
        Records request time for rate limiting.

        Args:
            url: URL to fetch

        Returns:
            Response object or None if error
        """
        try:
            # SSRF validation
            try:
                from apps.core.security import validate_url_ssrf
                try:
                    # validate_url_ssrf returns (validated_url, hostname, port)
                    url, _, _ = validate_url_ssrf(url)
                except Exception as exc:  # SSRFError or validation failure
                    logger.warning(f"SSRF blocked for {url}: {exc}")
                    return None
            except ImportError:
                pass  # Security module not available, proceed without check
            
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            # Add custom headers from source config
            if self.source.custom_headers:
                headers.update(self.source.custom_headers)
            
            # Optional TLS verification override for sources with broken certs
            verify_ssl = self.config.get('verify_ssl', True)
            if not verify_ssl:
                logger.warning(f"TLS verification disabled for {self.source.domain} (test mode)")

            response = requests.get(
                url,
                headers=headers,
                timeout=30,
                allow_redirects=True,
                verify=verify_ssl,
            )

            response.raise_for_status()
            
            # Record this request for rate limiting
            domain = urlparse(url).netloc
            self.rate_limiter.record_request(domain)
            
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

        url_lower = url.lower()

        # Domain-specific tuned rules from registry
        if self.rules:
            include = [p.lower() for p in self.rules.get("include_patterns", [])]
            exclude = [p.lower() for p in self.rules.get("exclude_patterns", [])]
            required_ext = [p.lower() for p in self.rules.get("require_extensions", [])]

            if exclude and any(p in url_lower for p in exclude):
                return False
            if required_ext and not any(url_lower.endswith(ext) for ext in required_ext):
                return False
            if include and not any(p in url_lower for p in include):
                return False

        # Exclude common non-article paths
        exclude_patterns = [
            '/category/', '/tag/', '/author/', '/page/',
            '/search/', '/archive/', '/about', '/contact',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js'
        ]
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
        Uses normalized URL for duplicate checking and storage.

        Args:
            url: Article URL

        Returns:
            Article instance or None
        """
        try:
            # Normalize URL for consistent duplicate checking
            normalized_url = self.url_normalizer.normalize(url)
            
            # Check if duplicate first (before fetching)
            if self._is_duplicate(normalized_url):
                return None

            # Fetch article page
            response = self._fetch_page(url)
            if not response:
                return None

            # Extract article data
            article_data = self._extract_article_data(response)
            if not article_data:
                return None

            # Save article with normalized URL
            article = self._save_article(
                url=normalized_url,
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
