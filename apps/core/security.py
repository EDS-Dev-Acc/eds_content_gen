"""
Security utilities for EMCIP.

Provides SSRF protection, URL validation, and safe HTTP client.
"""

import ipaddress
import re
import socket
from functools import lru_cache
from typing import Optional, Tuple, List, Set
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# =============================================================================
# SSRF Protection
# =============================================================================

class SSRFError(Exception):
    """Raised when a URL fails SSRF validation."""
    pass


class SSRFGuard:
    """
    SSRF (Server-Side Request Forgery) protection utility.
    
    Validates URLs and resolved IPs to prevent requests to internal networks,
    localhost, cloud metadata endpoints, and other dangerous destinations.
    """
    
    # Private IPv4 ranges (RFC 1918, RFC 5737, RFC 6598)
    PRIVATE_IPV4_RANGES = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),        # Loopback
        ipaddress.ip_network('169.254.0.0/16'),     # Link-local
        ipaddress.ip_network('0.0.0.0/8'),          # This network
        ipaddress.ip_network('100.64.0.0/10'),      # Carrier-grade NAT
        ipaddress.ip_network('192.0.0.0/24'),       # IETF Protocol Assignments
        ipaddress.ip_network('192.0.2.0/24'),       # TEST-NET-1
        ipaddress.ip_network('198.51.100.0/24'),    # TEST-NET-2
        ipaddress.ip_network('203.0.113.0/24'),     # TEST-NET-3
        ipaddress.ip_network('224.0.0.0/4'),        # Multicast
        ipaddress.ip_network('240.0.0.0/4'),        # Reserved
        ipaddress.ip_network('255.255.255.255/32'), # Broadcast
    ]
    
    # Private IPv6 ranges
    PRIVATE_IPV6_RANGES = [
        ipaddress.ip_network('::1/128'),            # Loopback
        ipaddress.ip_network('::/128'),             # Unspecified
        ipaddress.ip_network('fc00::/7'),           # Unique local
        ipaddress.ip_network('fe80::/10'),          # Link-local
        ipaddress.ip_network('ff00::/8'),           # Multicast
        ipaddress.ip_network('::ffff:0:0/96'),      # IPv4-mapped (check underlying)
    ]
    
    # Cloud metadata endpoints (AWS, GCP, Azure, etc.)
    BLOCKED_HOSTNAMES = {
        'metadata.google.internal',
        'metadata.goog',
        'kubernetes.default',
        'kubernetes.default.svc',
    }
    
    # Cloud metadata IP addresses
    BLOCKED_IPS = {
        '169.254.169.254',  # AWS/GCP/Azure metadata
        '169.254.170.2',    # AWS ECS task metadata
        'fd00:ec2::254',    # AWS IPv6 metadata
    }
    
    # Allowed protocols
    ALLOWED_PROTOCOLS = {'http', 'https'}
    
    # Dangerous ports to block
    BLOCKED_PORTS = {
        21,    # FTP
        22,    # SSH
        23,    # Telnet
        25,    # SMTP
        53,    # DNS
        110,   # POP3
        135,   # RPC
        139,   # NetBIOS
        143,   # IMAP
        445,   # SMB
        1433,  # MSSQL
        1521,  # Oracle
        3306,  # MySQL
        3389,  # RDP
        5432,  # PostgreSQL
        5900,  # VNC
        6379,  # Redis
        11211, # Memcached
        27017, # MongoDB
    }
    
    def __init__(
        self,
        allow_localhost: bool = False,
        allow_private_ips: bool = False,
        allowed_domains: Optional[Set[str]] = None,
        blocked_domains: Optional[Set[str]] = None,
        max_redirects: int = 5,
    ):
        """
        Initialize SSRF guard.
        
        Args:
            allow_localhost: Whether to allow localhost/127.0.0.1
            allow_private_ips: Whether to allow private IP ranges
            allowed_domains: Whitelist of allowed domains (if set, only these allowed)
            blocked_domains: Blacklist of blocked domains
            max_redirects: Maximum number of redirects to follow
        """
        self.allow_localhost = allow_localhost
        self.allow_private_ips = allow_private_ips
        self.allowed_domains = allowed_domains or set()
        self.blocked_domains = blocked_domains or set()
        self.max_redirects = max_redirects
    
    def validate_url(self, url: str) -> Tuple[str, str, int]:
        """
        Validate a URL for SSRF safety.
        
        Args:
            url: The URL to validate
            
        Returns:
            Tuple of (validated_url, hostname, port)
            
        Raises:
            SSRFError: If the URL is not safe
        """
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SSRFError(f"Invalid URL format: {e}")
        
        # Check protocol
        if parsed.scheme.lower() not in self.ALLOWED_PROTOCOLS:
            raise SSRFError(f"Protocol '{parsed.scheme}' not allowed. Use HTTP or HTTPS.")
        
        # Check for empty hostname
        hostname = parsed.hostname
        if not hostname:
            raise SSRFError("URL must have a hostname")
        
        # Get port (default based on scheme)
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme.lower() == 'https' else 80
        
        # Check blocked ports
        if port in self.BLOCKED_PORTS:
            raise SSRFError(f"Port {port} is blocked for security reasons")
        
        # Check hostname against blocked list
        hostname_lower = hostname.lower()
        if hostname_lower in self.BLOCKED_HOSTNAMES:
            raise SSRFError(f"Hostname '{hostname}' is blocked")
        
        # Check domain whitelist/blacklist
        if self.allowed_domains and not self._domain_matches(hostname_lower, self.allowed_domains):
            raise SSRFError(f"Domain '{hostname}' not in allowed list")
        
        if self._domain_matches(hostname_lower, self.blocked_domains):
            raise SSRFError(f"Domain '{hostname}' is blocked")
        
        # Resolve hostname and validate IPs
        self._validate_resolved_ips(hostname)
        
        return url, hostname, port
    
    def _domain_matches(self, hostname: str, domain_set: Set[str]) -> bool:
        """Check if hostname matches any domain in the set (including subdomains)."""
        for domain in domain_set:
            if hostname == domain or hostname.endswith('.' + domain):
                return True
        return False
    
    def _validate_resolved_ips(self, hostname: str) -> List[str]:
        """
        Resolve hostname and validate all resulting IPs.
        
        Returns:
            List of resolved IP addresses
            
        Raises:
            SSRFError: If any resolved IP is not safe
        """
        try:
            # Get all IP addresses for hostname
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
            ips = list(set(info[4][0] for info in addr_info))
        except socket.gaierror as e:
            raise SSRFError(f"Could not resolve hostname '{hostname}': {e}")
        
        if not ips:
            raise SSRFError(f"No IP addresses found for hostname '{hostname}'")
        
        # Validate each IP
        for ip_str in ips:
            self._validate_ip(ip_str)
        
        return ips
    
    def _validate_ip(self, ip_str: str) -> None:
        """
        Validate a single IP address.
        
        Raises:
            SSRFError: If the IP is not safe
        """
        # Check against blocked IPs
        if ip_str in self.BLOCKED_IPS:
            raise SSRFError(f"IP address '{ip_str}' is blocked (cloud metadata)")
        
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFError(f"Invalid IP address: {ip_str}")
        
        # Check for private ranges
        if not self.allow_private_ips:
            if isinstance(ip, ipaddress.IPv4Address):
                for network in self.PRIVATE_IPV4_RANGES:
                    if ip in network:
                        if not (self.allow_localhost and ip.is_loopback):
                            raise SSRFError(
                                f"IP address '{ip_str}' is in private range {network}"
                            )
            elif isinstance(ip, ipaddress.IPv6Address):
                for network in self.PRIVATE_IPV6_RANGES:
                    if ip in network:
                        if not (self.allow_localhost and ip.is_loopback):
                            raise SSRFError(
                                f"IP address '{ip_str}' is in private range {network}"
                            )


# =============================================================================
# URL Normalization
# =============================================================================

class URLNormalizer:
    """
    URL normalization for deduplication.
    
    Normalizes URLs to a canonical form for comparison and storage.
    """
    
    # Query parameters to strip (tracking/analytics)
    STRIP_PARAMS = {
        # UTM parameters
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
        # Facebook
        'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_source', 'fb_ref',
        # Google
        'gclid', 'gclsrc', 'dclid',
        # Other trackers
        'ref', 'ref_src', 'referer', 'source', 'mc_cid', 'mc_eid',
        '_ga', '_gl', '_hsenc', '_hsmi', 'hsCtaTracking',
        'mkt_tok', 'trk', 'trkInfo', 'li_fat_id',
        'msclkid', 'igshid', 'si', 's_kwcid', 'ss_source', 'ss_campaign_id',
    }
    
    # Default ports by scheme
    DEFAULT_PORTS = {
        'http': 80,
        'https': 443,
    }
    
    @classmethod
    def normalize(cls, url: str, strip_fragments: bool = True, 
                  strip_tracking: bool = True, lowercase_path: bool = False) -> str:
        """
        Normalize a URL to canonical form.
        
        Args:
            url: URL to normalize
            strip_fragments: Remove URL fragments (#anchor)
            strip_tracking: Remove tracking query parameters
            lowercase_path: Convert path to lowercase (risky for case-sensitive servers)
            
        Returns:
            Normalized URL string
        """
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return url  # Return as-is if unparseable
        
        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower() if parsed.hostname else ''
        
        # Remove default port
        port = parsed.port
        if port and cls.DEFAULT_PORTS.get(scheme) == port:
            port = None
        
        # Build netloc
        netloc = hostname
        if port:
            netloc = f"{hostname}:{port}"
        if parsed.username:
            userinfo = parsed.username
            if parsed.password:
                userinfo += f":{parsed.password}"
            netloc = f"{userinfo}@{netloc}"
        
        # Normalize path
        path = parsed.path or '/'
        
        # Remove duplicate slashes
        path = re.sub(r'/+', '/', path)
        
        # Optional lowercase
        if lowercase_path:
            path = path.lower()
        
        # Remove trailing slash (except for root)
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        
        # Handle query string
        query = ''
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            if strip_tracking:
                params = {k: v for k, v in params.items() 
                         if k.lower() not in cls.STRIP_PARAMS}
            if params:
                # Sort params for consistency
                sorted_params = sorted(params.items())
                query = urlencode(sorted_params, doseq=True)
        
        # Handle fragment
        fragment = '' if strip_fragments else parsed.fragment
        
        # Reconstruct URL
        normalized = urlunparse((scheme, netloc, path, '', query, fragment))
        
        return normalized
    
    @classmethod
    def extract_domain(cls, url: str) -> str:
        """Extract the domain from a URL."""
        try:
            parsed = urlparse(url)
            return parsed.hostname.lower() if parsed.hostname else ''
        except Exception:
            return ''
    
    @classmethod
    def extract_base_url(cls, url: str) -> str:
        """Extract scheme://hostname from a URL."""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.hostname}"
        except Exception:
            return url


# =============================================================================
# Safe HTTP Client
# =============================================================================

class SafeHTTPClient:
    """
    HTTP client with SSRF protection and connection pooling.
    
    Provides a safe way to make external HTTP requests with:
    - SSRF validation on all URLs
    - Connection pooling for performance
    - Retry logic with exponential backoff
    - Timeouts and content length limits
    - Content type validation
    """
    
    # Default timeouts (connect, read)
    DEFAULT_TIMEOUT = (5, 30)
    
    # Maximum content length (10 MB)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    
    # Allowed content types for HTML/text
    ALLOWED_CONTENT_TYPES = {
        'text/html',
        'text/plain',
        'application/xhtml+xml',
        'application/xml',
        'text/xml',
        'application/json',
        'application/rss+xml',
        'application/atom+xml',
    }
    
    _session: Optional[requests.Session] = None
    _ssrf_guard: Optional[SSRFGuard] = None
    
    def __init__(
        self,
        timeout: Tuple[int, int] = DEFAULT_TIMEOUT,
        max_content_length: int = MAX_CONTENT_LENGTH,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        ssrf_guard: Optional[SSRFGuard] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize safe HTTP client.
        
        Args:
            timeout: (connect_timeout, read_timeout) in seconds
            max_content_length: Maximum response content length in bytes
            max_retries: Number of retries on failure
            backoff_factor: Exponential backoff factor
            ssrf_guard: Custom SSRF guard instance
            user_agent: Custom User-Agent string
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.ssrf_guard = ssrf_guard or SSRFGuard()
        self.user_agent = user_agent or (
            'Mozilla/5.0 (compatible; EMCIPBot/1.0; +https://example.com/bot)'
        )
        
        # Create session with retry adapter
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        return session
    
    def head(self, url: str, **kwargs) -> requests.Response:
        """
        Make a safe HEAD request.
        
        Args:
            url: URL to request
            **kwargs: Additional requests kwargs
            
        Returns:
            Response object
            
        Raises:
            SSRFError: If URL fails SSRF validation
        """
        self.ssrf_guard.validate_url(url)
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('allow_redirects', True)
        return self.session.head(url, **kwargs)
    
    def get(
        self,
        url: str,
        validate_content_type: bool = True,
        stream: bool = False,
        **kwargs
    ) -> requests.Response:
        """
        Make a safe GET request.
        
        Args:
            url: URL to request
            validate_content_type: Check Content-Type header
            stream: Stream response (for large files)
            **kwargs: Additional requests kwargs
            
        Returns:
            Response object
            
        Raises:
            SSRFError: If URL fails SSRF validation
            ValueError: If content type or length is invalid
        """
        self.ssrf_guard.validate_url(url)
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('allow_redirects', True)
        
        if stream:
            kwargs['stream'] = True
            response = self.session.get(url, **kwargs)
            self._validate_response(response, validate_content_type)
            return response
        else:
            response = self.session.get(url, **kwargs)
            self._validate_response(response, validate_content_type)
            return response
    
    def _validate_response(self, response: requests.Response, 
                           validate_content_type: bool = True) -> None:
        """Validate response headers."""
        # Check content length
        content_length = response.headers.get('Content-Length')
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_content_length:
                    raise ValueError(
                        f"Content too large: {length} bytes "
                        f"(max: {self.max_content_length})"
                    )
            except ValueError:
                pass
        
        # Check content type
        if validate_content_type:
            content_type = response.headers.get('Content-Type', '')
            # Extract mime type (strip charset etc)
            mime_type = content_type.split(';')[0].strip().lower()
            if mime_type and mime_type not in self.ALLOWED_CONTENT_TYPES:
                logger.warning(f"Unexpected content type: {content_type} for {response.url}")
    
    def fetch_with_limit(self, url: str, max_bytes: Optional[int] = None) -> bytes:
        """
        Fetch URL content with byte limit.
        
        Args:
            url: URL to fetch
            max_bytes: Maximum bytes to read (defaults to max_content_length)
            
        Returns:
            Response content as bytes
        """
        max_bytes = max_bytes or self.max_content_length
        
        response = self.get(url, stream=True)
        response.raise_for_status()
        
        chunks = []
        total = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Response exceeds {max_bytes} byte limit")
            chunks.append(chunk)
        
        return b''.join(chunks)
    
    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =============================================================================
# Singleton Safe Client
# =============================================================================

_default_client: Optional[SafeHTTPClient] = None


def get_safe_client() -> SafeHTTPClient:
    """Get the default safe HTTP client singleton."""
    global _default_client
    if _default_client is None:
        _default_client = SafeHTTPClient()
    return _default_client


def safe_head(url: str, **kwargs) -> requests.Response:
    """Convenience function for safe HEAD request."""
    return get_safe_client().head(url, **kwargs)


def safe_get(url: str, **kwargs) -> requests.Response:
    """Convenience function for safe GET request."""
    return get_safe_client().get(url, **kwargs)


def validate_url_ssrf(url: str) -> Tuple[str, str, int]:
    """Convenience function to validate URL for SSRF."""
    return get_safe_client().ssrf_guard.validate_url(url)


def normalize_url(url: str) -> str:
    """Convenience function to normalize a URL."""
    return URLNormalizer.normalize(url)
