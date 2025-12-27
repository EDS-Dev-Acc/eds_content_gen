"""
Modular crawler using pluggable interfaces.

This crawler uses the new abstraction layer (Fetcher, LinkExtractor, Paginator)
while maintaining compatibility with the existing ScrapyCrawler behavior.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..base import BaseCrawler
from ..extractors import BS4LinkExtractor
from ..fetchers import HTTPFetcher
from ..interfaces import CrawlerPipeline, FetchResult, Fetcher, LinkExtractor, Paginator
from ..pagination import AdaptivePaginator, create_paginator
from ..registry import get_pagination_config, get_rules_for_domain
from ..utils import URLDeduplicator, URLNormalizer
from ..exceptions import CrawlCancelled

logger = logging.getLogger(__name__)


class ModularCrawler(BaseCrawler):
    """
    Crawler using pluggable components.
    
    This is a refactored version of ScrapyCrawler that uses:
    - Fetcher interface for HTTP requests
    - LinkExtractor interface for parsing links
    - Paginator interface for pagination strategies
    
    The components can be swapped out for different implementations
    (e.g., Playwright fetcher for JS-heavy sites).
    """
    
    def __init__(
        self,
        source,
        fetcher: Optional[Fetcher] = None,
        link_extractor: Optional[LinkExtractor] = None,
        paginator: Optional[Paginator] = None,
        config: dict = None,
    ):
        super().__init__(source, config=config)
        
        # Load domain-specific rules
        self.rules = get_rules_for_domain(source.domain)
        self.pagination_config = get_pagination_config(source.domain)
        
        # Initialize URL utilities
        self.url_normalizer = URLNormalizer(
            remove_trailing_slash=True,
            remove_fragments=True,
            remove_tracking_params=True,
        )
        self.url_deduplicator = URLDeduplicator(self.url_normalizer)
        
        # Build headers
        self._headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        if source.custom_headers:
            self._headers.update(source.custom_headers)
        
        # Initialize components (use defaults if not provided)
        self.fetcher = fetcher or HTTPFetcher(
            headers=self._headers,
            timeout=30,
            rate_limit_delay=self.delay,
        )
        
        self.link_extractor = link_extractor or BS4LinkExtractor(
            min_path_segments=2,
        )
        
        # Create paginator based on config
        self.paginator = paginator or self._create_paginator()
        
        # Async fetch settings
        self.use_async_fetch = self.config.get('use_async_fetch', True)
        self.max_concurrent = self.config.get('max_concurrent', 5)
    
    def _create_paginator(self) -> Paginator:
        """Create paginator from source configuration or past success."""
        max_pages = self.pagination_config.get('max_pages', self.max_pages)
        
        # Check if source has a successful pagination strategy
        preferred = self.source.get_preferred_paginator_config()
        if preferred:
            strategy = preferred.get('strategy')
            logger.info(f"Using previously successful strategy: {strategy}")
            
            if strategy == 'parameter':
                return create_paginator(
                    'parameter',
                    param_name=preferred.get('param_name', 'page'),
                    start_page=preferred.get('start_page', 1),
                    max_pages=max_pages,
                )
            elif strategy == 'path':
                return create_paginator(
                    'path',
                    pattern=preferred.get('pattern', '/page/{page}/'),
                    start_page=preferred.get('start_page', 1),
                    max_pages=max_pages,
                )
            elif strategy == 'next_link':
                return create_paginator('next_link', max_pages=max_pages)
        
        # Fall back to registry configuration
        pagination_type = self.pagination_config['pagination_type']
        
        if pagination_type == 'param':
            return create_paginator(
                'parameter',
                param_name=self.pagination_config.get('page_param', 'page'),
                start_page=self.pagination_config.get('start_page', 1),
                max_pages=max_pages,
            )
        elif pagination_type == 'path':
            return create_paginator(
                'path',
                pattern=self.pagination_config.get('page_path_format', '/page/{page}/'),
                start_page=self.pagination_config.get('start_page', 1),
                max_pages=max_pages,
            )
        elif pagination_type == 'next_link':
            return create_paginator('next_link', max_pages=max_pages)
        else:
            # Use adaptive paginator by default
            return create_paginator('adaptive', max_pages=max_pages)
    
    def crawl(self) -> Dict[str, Any]:
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
            'article_ids': [],
            'pages_crawled': 0,
        }
        
        try:
            logger.info(f"Starting modular crawl of {self.source.name} ({self.source.url})")
            self._raise_if_cancelled()
            
            # Phase 1: Collect article links with pagination
            article_links = self._crawl_with_pagination()
            results['total_found'] = len(article_links)
            results['pages_crawled'] = self._pages_crawled
            
            logger.info(
                f"Found {len(article_links)} potential articles "
                f"across {self._pages_crawled} pages"
            )
            
            # Phase 2: Process articles
            max_articles = self.config.get('max_articles', 50)
            articles_to_process = article_links[:max_articles]
            
            if self.use_async_fetch and len(articles_to_process) > 1:
                results = self._process_articles_parallel(articles_to_process, results)
            else:
                results = self._process_articles_sequential(articles_to_process, results)
            
            logger.info(
                f"Crawl complete: {results['new_articles']} new, "
                f"{results['duplicates']} duplicates from {results['pages_crawled']} pages"
            )
            
            # Phase 3: Persist successful pagination strategy
            if results['pages_crawled'] > 1 and results['new_articles'] > 0:
                self._save_pagination_success(results['pages_crawled'])
            
        except CrawlCancelled:
            logger.info("Crawl cancelled for %s", self.source.name)
            raise
        except Exception as e:
            logger.error(f"Error during crawl: {e}")
            results['errors'] += 1
            self.source.last_error_message = str(e)
            self.source.save()
        
        finally:
            self._update_source_stats(results)
        
        return results
    
    def _save_pagination_success(self, pages_crawled: int):
        """Save the successful pagination strategy to the source."""
        try:
            state = self.paginator.get_state()
            strategy_type = state.get('type', 'unknown')
            
            # Extract detected params based on strategy type
            detected_params = {}
            if strategy_type == 'parameter':
                detected_params = {
                    'param_name': state.get('param_name', 'page'),
                    'start_page': state.get('start_page', 1),
                }
            elif strategy_type == 'path':
                detected_params = {
                    'pattern': state.get('pattern', '/page/{page}/'),
                    'start_page': state.get('start_page', 1),
                }
            elif strategy_type == 'adaptive':
                # Get inner strategy details
                inner = state.get('detected_strategy', {})
                strategy_type = inner.get('type', 'adaptive')
                if inner.get('param_name'):
                    detected_params['param_name'] = inner['param_name']
                if inner.get('pattern'):
                    detected_params['pattern'] = inner['pattern']
            
            self.source.record_pagination_success(
                strategy_type=strategy_type,
                pages_crawled=pages_crawled,
                detected_params=detected_params,
            )
            logger.info(f"Saved pagination success: {strategy_type} ({pages_crawled} pages)")
            
        except Exception as e:
            logger.warning(f"Failed to save pagination state: {e}")
    
    def _crawl_with_pagination(self) -> List[str]:
        """
        Crawl multiple pages using the configured paginator.
        
        Returns:
            List of unique normalized article URLs
        """
        all_links = []
        current_url = self.source.url
        self._pages_crawled = 0
        
        # Reset paginator state
        self.paginator.reset()
        
        while self._pages_crawled < self.max_pages:
            self._raise_if_cancelled()
            # Fetch the current page
            result = self.fetcher.fetch(current_url)
            
            if not result.success:
                logger.warning(
                    f"Failed to fetch page {self._pages_crawled + 1}: "
                    f"{result.error}"
                )
                break
            
            self._pages_crawled += 1
            logger.debug(f"Crawling page {self._pages_crawled}: {current_url}")
            
            # Extract links from the page
            domain = self.source.domain
            extracted_links = self.link_extractor.extract_links(
                result.html, 
                current_url,
                domain=domain,
            )
            
            # Filter for article-like links
            article_links = self.link_extractor.filter_article_links(
                extracted_links,
                rules=self.rules,
            )
            
            # Deduplicate
            new_links_count = 0
            for link in article_links:
                self._raise_if_cancelled()
                normalized = self.url_deduplicator.add_if_new(link.url)
                if normalized:
                    all_links.append(normalized)
                    new_links_count += 1
            
            logger.info(
                f"Page {self._pages_crawled}: found {len(extracted_links)} links, "
                f"{new_links_count} new articles"
            )
            
            # Check if we should continue pagination
            if new_links_count == 0 and self._pages_crawled > 1:
                logger.info("No new links found, stopping pagination")
                break
            
            # Get next page
            pagination_result = self.paginator.next_page(
                current_url,
                html=result.html,
            )
            
            if not pagination_result.has_more or not pagination_result.url:
                logger.debug("No more pages, stopping pagination")
                break
            
            current_url = pagination_result.url
        
        logger.info(
            f"Pagination complete: {self._pages_crawled} pages, "
            f"{len(all_links)} unique articles"
        )
        
        return all_links
    
    def _process_articles_sequential(
        self, 
        urls: List[str], 
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process articles one at a time.
        """
        for url in urls:
            self._raise_if_cancelled()
            # Check for duplicate before fetching
            normalized = self.url_normalizer.normalize(url)
            if self._is_duplicate(normalized):
                results['duplicates'] += 1
                continue
            
            # Fetch and process
            article = self._process_single_article(url)
            if article:
                results['new_articles'] += 1
                results['article_ids'].append(str(article.id))
        
        return results
    
    def _process_articles_parallel(
        self, 
        urls: List[str], 
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process articles in parallel using async fetching.
        """
        # Filter out duplicates first
        urls_to_fetch = []
        for url in urls:
            self._raise_if_cancelled()
            normalized = self.url_normalizer.normalize(url)
            if self._is_duplicate(normalized):
                results['duplicates'] += 1
            else:
                urls_to_fetch.append(url)
        
        if not urls_to_fetch:
            return results
        
        logger.info(
            f"Parallel fetching {len(urls_to_fetch)} articles "
            f"(max concurrent: {self.max_concurrent})"
        )
        
        # Fetch all URLs
        fetch_results = self.fetcher.fetch_many(
            urls_to_fetch,
            max_concurrent=self.max_concurrent,
        )
        
        # Process results
        for result in fetch_results:
            self._raise_if_cancelled()
            if not result.success:
                logger.debug(f"Error fetching {result.url}: {result.error}")
                continue
            
            # Extract and save article
            article_data = self._extract_article_data_from_html(result.url, result.html)
            if article_data:
                article = self._save_article(
                    url=self.url_normalizer.normalize(result.url),
                    title=article_data['title'],
                    html=result.html,
                    metadata=article_data.get('metadata', {}),
                )
                if article:
                    results['new_articles'] += 1
                    results['article_ids'].append(str(article.id))
        
        return results
    
    def _process_single_article(self, url: str):
        """
        Fetch and process a single article.
        """
        try:
            result = self.fetcher.fetch(url)
            if not result.success:
                return None
            
            article_data = self._extract_article_data_from_html(url, result.html)
            if not article_data:
                return None
            
            return self._save_article(
                url=self.url_normalizer.normalize(url),
                title=article_data['title'],
                html=result.html,
                metadata=article_data.get('metadata', {}),
            )
            
        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")
            return None
    
    def _extract_article_data_from_html(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """
        Extract article data from HTML content.
        """
        # Use the link extractor's metadata extraction
        metadata = self.link_extractor.extract_metadata(html)
        
        if not metadata.get('title'):
            logger.warning(f"No title found for {url}")
            return None
        
        return {
            'title': metadata['title'],
            'metadata': {
                'url': url,
                'author': metadata.get('author'),
                'published_date_str': metadata.get('published_date'),
                'description': metadata.get('description'),
            },
        }
