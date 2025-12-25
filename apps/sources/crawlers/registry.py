"""
Registry of site-specific crawler tuning rules.

Each entry can define:
- include_patterns: list of substrings that should appear in article URLs
- exclude_patterns: list of substrings that should exclude a URL
- require_extensions: list of extensions (e.g., [".html"]) that URLs must end with

Pagination options:
- pagination_type: 'param' (URL parameter), 'path' (URL path), 'next_link' (follow link), 'none'
- page_param: query parameter name for pagination (default: 'page')
- page_path_format: URL path format for pagination (e.g., '/page/{page}/')
- next_link_selector: CSS selector for "next page" link
- start_page: starting page number (default: 1)
- page_increment: how much to increment page (default: 1)
- max_pages: maximum pages to crawl per session

Fetcher options:
- fetcher_type: 'http' (default), 'browser' (Playwright), 'hybrid'
- requires_javascript: True if site needs JS rendering

Add a new entry keyed by domain to tune a site without hard-coding in the crawler.
"""

from typing import Optional

TUNED_CRAWLERS = {
    # Example: Vietnam News economy site - uses query parameter pagination
    "vietnamnews.vn": {
        "include_patterns": ["/economy/"],
        "exclude_patterns": ["/topic/"],
        "require_extensions": [".html"],
        "pagination_type": "param",
        "page_param": "page",
        "start_page": 1,
        "max_pages": 10,
    },
    # Example: Site with path-based pagination (e.g., /news/page/2/)
    # "example.com": {
    #     "pagination_type": "path",
    #     "page_path_format": "/page/{page}/",
    #     "start_page": 1,
    # },
    # Example: Site with "next page" link
    # "blog.example.com": {
    #     "pagination_type": "next_link",
    #     "next_link_selector": "a.next-page, a[rel='next']",
    # },
    # Example: Site requiring JavaScript
    # "spa-site.com": {
    #     "fetcher_type": "browser",
    #     "requires_javascript": True,
    #     "pagination_type": "next_link",
    # },
    # Add more tuned sites here as needed.
}


def get_rules_for_domain(domain: str) -> dict:
    """Return tuning rules for the given domain, if present."""
    if not domain:
        return {}
    return TUNED_CRAWLERS.get(domain.lower(), {})


def get_pagination_config(domain: str) -> dict:
    """
    Get pagination configuration for a domain with sensible defaults.
    
    Returns:
        dict with pagination settings:
        - pagination_type: 'param', 'path', 'next_link', or 'none'
        - page_param: query parameter name (for 'param' type)
        - page_path_format: URL path format (for 'path' type)
        - next_link_selector: CSS selector (for 'next_link' type)
        - start_page: starting page number
        - page_increment: page increment value
        - max_pages: maximum pages to crawl
    """
    rules = get_rules_for_domain(domain)
    
    return {
        'pagination_type': rules.get('pagination_type', 'param'),
        'page_param': rules.get('page_param', 'page'),
        'page_path_format': rules.get('page_path_format', '/page/{page}/'),
        'next_link_selector': rules.get('next_link_selector', 'a.next, a[rel="next"], .pagination a.next'),
        'start_page': rules.get('start_page', 1),
        'page_increment': rules.get('page_increment', 1),
        'max_pages': rules.get('max_pages', 10),
    }


def get_fetcher_config(domain: str) -> dict:
    """
    Get fetcher configuration for a domain.
    
    Returns:
        dict with fetcher settings:
        - fetcher_type: 'http', 'browser', or 'hybrid'
        - requires_javascript: whether JS rendering is needed
        - timeout: request timeout in seconds
    """
    rules = get_rules_for_domain(domain)
    
    return {
        'fetcher_type': rules.get('fetcher_type', 'http'),
        'requires_javascript': rules.get('requires_javascript', False),
        'timeout': rules.get('timeout', 30),
    }


def get_combined_config(source) -> dict:
    """
    Get combined configuration from registry, source model, and pagination state.
    
    Priority (highest to lowest):
    1. Source pagination_state (learned from successful crawls)
    2. Registry TUNED_CRAWLERS
    3. Source crawler_config
    4. Defaults
    
    Args:
        source: Source model instance
        
    Returns:
        dict with complete crawler configuration
    """
    domain = source.domain
    
    # Start with defaults
    config = {
        # Pagination
        'pagination_type': 'adaptive',
        'page_param': 'page',
        'page_path_format': '/page/{page}/',
        'next_link_selector': 'a.next, a[rel="next"], .pagination a.next',
        'start_page': 1,
        'max_pages': 10,
        
        # Fetcher
        'fetcher_type': 'http',
        'requires_javascript': source.requires_javascript,
        'timeout': 30,
        
        # Rate limiting
        'delay': 2.0,
        'max_concurrent': 5,
        
        # Link filtering
        'include_patterns': [],
        'exclude_patterns': [],
        'require_extensions': [],
    }
    
    # Layer 1: Source crawler_config
    if source.crawler_config:
        config.update(source.crawler_config)
    
    # Layer 2: Registry rules
    registry_rules = get_rules_for_domain(domain)
    if registry_rules:
        config.update(registry_rules)
    
    # Layer 3: Pagination state (learned strategy)
    if source.pagination_state:
        state = source.pagination_state
        if state.get('strategy_type'):
            # Map strategy_type to pagination_type
            strategy = state['strategy_type']
            if strategy in ('parameter', 'param'):
                config['pagination_type'] = 'param'
            elif strategy in ('path',):
                config['pagination_type'] = 'path'
            elif strategy in ('next_link',):
                config['pagination_type'] = 'next_link'
            
            # Apply detected params
            params = state.get('detected_params', {})
            if params.get('param_name'):
                config['page_param'] = params['param_name']
            if params.get('pattern'):
                config['page_path_format'] = params['pattern']
            if params.get('start_page'):
                config['start_page'] = params['start_page']
    
    return config


def register_site(domain: str, rules: dict):
    """
    Dynamically register or update rules for a domain.
    
    Args:
        domain: Domain name (e.g., 'example.com')
        rules: Dict of rules to apply
    """
    TUNED_CRAWLERS[domain.lower()] = rules


def unregister_site(domain: str):
    """Remove rules for a domain."""
    TUNED_CRAWLERS.pop(domain.lower(), None)
