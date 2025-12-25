"""
Tests for SSRF Guard - Critical Security Tests.

Phase 17: Production hardening - SSRF protection validation.

Tests cover:
- IP blocking (private, loopback, link-local ranges)
- Port blocking (dangerous ports)
- URL normalization bypass attempts
- DNS rebinding resistance
- IPv6 blocking
"""

import pytest
import ipaddress
from unittest.mock import patch, MagicMock
from apps.core.security import (
    SSRFGuard,
    SSRFError,
    SafeHTTPClient,
)


# ============================================================================
# IP Validation Tests
# ============================================================================

class TestIPValidation:
    """Test IP address validation."""
    
    def test_loopback_ipv4_blocked(self):
        """127.0.0.1 and localhost should be blocked."""
        guard = SSRFGuard()
        
        for ip in ['127.0.0.1', '127.0.0.2', '127.255.255.255']:
            with pytest.raises(SSRFError):
                guard._validate_ip(ip)
    
    def test_private_class_a_blocked(self):
        """10.x.x.x range should be blocked."""
        guard = SSRFGuard()
        
        for ip in ['10.0.0.1', '10.255.255.255']:
            with pytest.raises(SSRFError):
                guard._validate_ip(ip)
    
    def test_private_class_b_blocked(self):
        """172.16-31.x.x range should be blocked."""
        guard = SSRFGuard()
        
        # Should be blocked
        for ip in ['172.16.0.1', '172.31.255.255']:
            with pytest.raises(SSRFError):
                guard._validate_ip(ip)
        
        # Just outside the range - should be allowed
        for ip in ['172.15.255.255', '172.32.0.1']:
            guard._validate_ip(ip)  # Should not raise
    
    def test_private_class_c_blocked(self):
        """192.168.x.x range should be blocked."""
        guard = SSRFGuard()
        
        for ip in ['192.168.0.1', '192.168.255.255']:
            with pytest.raises(SSRFError):
                guard._validate_ip(ip)
    
    def test_link_local_blocked(self):
        """169.254.x.x (link-local) should be blocked."""
        guard = SSRFGuard()
        
        for ip in ['169.254.169.254', '169.254.1.1']:
            with pytest.raises(SSRFError):
                guard._validate_ip(ip)
    
    def test_public_ip_allowed(self):
        """Public IPs should be allowed."""
        guard = SSRFGuard()
        
        for ip in ['8.8.8.8', '1.1.1.1', '93.184.216.34']:
            guard._validate_ip(ip)  # Should not raise


class TestIPv6Validation:
    """Test IPv6 address blocking."""
    
    def test_ipv6_loopback_blocked(self):
        """::1 should be blocked."""
        guard = SSRFGuard()
        
        with pytest.raises(SSRFError):
            guard._validate_ip('::1')
    
    def test_ipv6_private_blocked(self):
        """Private IPv6 ranges should be blocked."""
        guard = SSRFGuard()
        
        for ip in ['fc00::1', 'fd00::1', 'fe80::1']:
            with pytest.raises(SSRFError):
                guard._validate_ip(ip)


# ============================================================================
# Port Validation Tests
# ============================================================================

class TestPortBlocking:
    """Test port blocking for dangerous services."""
    
    def test_common_dangerous_ports_blocked(self):
        """Common dangerous ports should be blocked."""
        guard = SSRFGuard()
        
        dangerous_ports = [22, 23, 25, 110, 143, 445, 3306, 5432, 6379, 27017]
        for port in dangerous_ports:
            assert port in guard.BLOCKED_PORTS, f"Port {port} should be in BLOCKED_PORTS"
    
    def test_http_https_allowed(self):
        """HTTP/HTTPS ports should be allowed."""
        guard = SSRFGuard()
        
        assert 80 not in guard.BLOCKED_PORTS
        assert 443 not in guard.BLOCKED_PORTS


# ============================================================================
# URL Validation Tests
# ============================================================================

class TestURLValidation:
    """Test URL validation."""
    
    @patch('socket.getaddrinfo')
    def test_public_url_allowed(self, mock_dns):
        """Public URLs should pass validation."""
        guard = SSRFGuard()
        
        # Mock DNS to return public IP
        mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]
        
        result = guard.validate_url('https://www.example.com/')
        assert result is not None
    
    @patch('socket.getaddrinfo')
    def test_private_url_blocked(self, mock_dns):
        """Private URLs should be blocked."""
        guard = SSRFGuard()
        
        # Mock DNS to return private IP
        mock_dns.return_value = [(2, 1, 0, '', ('192.168.1.1', 80))]
        
        with pytest.raises(SSRFError):
            guard.validate_url('http://internal.company.com/')
    
    def test_invalid_scheme_blocked(self):
        """Non-HTTP schemes should be blocked."""
        guard = SSRFGuard()
        
        with pytest.raises(SSRFError):
            guard.validate_url('file:///etc/passwd')
        
        with pytest.raises(SSRFError):
            guard.validate_url('gopher://localhost/')
        
        with pytest.raises(SSRFError):
            guard.validate_url('ftp://example.com/')
    
    def test_blocked_port_in_url(self):
        """URLs with blocked ports should be rejected."""
        guard = SSRFGuard()
        
        with pytest.raises(SSRFError):
            guard.validate_url('http://example.com:22/')  # SSH
        
        with pytest.raises(SSRFError):
            guard.validate_url('http://example.com:3306/')  # MySQL


class TestMetadataEndpoints:
    """Test cloud metadata endpoint blocking."""
    
    def test_aws_metadata_ip_blocked(self):
        """AWS metadata IP should be blocked."""
        guard = SSRFGuard()
        
        with pytest.raises(SSRFError):
            guard._validate_ip('169.254.169.254')
    
    def test_metadata_hostname_blocked(self):
        """Cloud metadata hostnames should be blocked."""
        guard = SSRFGuard()
        
        blocked_hosts = ['metadata.google.internal', 'metadata.goog']
        for host in blocked_hosts:
            assert host in guard.BLOCKED_HOSTNAMES


# ============================================================================
# URL Parsing Attack Resistance
# ============================================================================

class TestURLParsing:
    """Test resistance to URL parsing attacks."""
    
    @patch('socket.getaddrinfo')
    def test_username_bypass_attempt(self, mock_dns):
        """URLs with @ to bypass domain should be handled."""
        guard = SSRFGuard()
        
        # Mock DNS to return loopback
        mock_dns.return_value = [(2, 1, 0, '', ('127.0.0.1', 80))]
        
        # Attacker might try: http://google.com@127.0.0.1/
        # Python's urlparse correctly extracts 127.0.0.1 as hostname
        with pytest.raises(SSRFError):
            guard.validate_url('http://google.com@127.0.0.1/')


# ============================================================================
# DNS Rebinding Resistance
# ============================================================================

class TestDNSRebinding:
    """Test DNS rebinding attack resistance."""
    
    @patch('socket.getaddrinfo')
    def test_dns_resolution_checked(self, mock_dns):
        """DNS is resolved and IP is checked before request."""
        guard = SSRFGuard()
        
        # First resolution returns private IP
        mock_dns.return_value = [(2, 1, 0, '', ('192.168.1.1', 80))]
        
        with pytest.raises(SSRFError) as exc_info:
            guard.validate_url('http://evil.example.com/')
        
        assert 'private' in str(exc_info.value).lower()
    
    @patch('socket.getaddrinfo')
    def test_multiple_ips_all_checked(self, mock_dns):
        """All resolved IPs should be checked, not just the first."""
        guard = SSRFGuard()
        
        # Returns both public and private - should block
        mock_dns.return_value = [
            (2, 1, 0, '', ('8.8.8.8', 80)),
            (2, 1, 0, '', ('127.0.0.1', 80)),
        ]
        
        with pytest.raises(SSRFError):
            guard.validate_url('http://dual.example.com/')


# ============================================================================
# Configuration Tests
# ============================================================================

class TestSSRFGuardConfiguration:
    """Test SSRFGuard configuration options."""
    
    def test_allow_localhost_option(self):
        """allow_localhost should permit loopback IPs."""
        guard = SSRFGuard(allow_localhost=True, allow_private_ips=True)
        
        # Should not raise with allow_localhost
        guard._validate_ip('127.0.0.1')
    
    def test_allow_private_ips_option(self):
        """allow_private_ips should permit private ranges."""
        guard = SSRFGuard(allow_private_ips=True)
        
        # Should not raise with allow_private_ips
        guard._validate_ip('192.168.1.1')
        guard._validate_ip('10.0.0.1')
    
    def test_blocked_domains_option(self):
        """blocked_domains should block specified domains."""
        guard = SSRFGuard(blocked_domains={'evil.com'})
        
        assert guard._domain_matches('evil.com', guard.blocked_domains)
        assert guard._domain_matches('sub.evil.com', guard.blocked_domains)
        assert not guard._domain_matches('notevil.com', guard.blocked_domains)


# ============================================================================
# SafeHTTPClient Tests
# ============================================================================

class TestSafeHTTPClient:
    """Test the SafeHTTPClient wrapper."""
    
    @patch('socket.getaddrinfo')
    @patch('requests.Session.get')
    def test_validation_before_request(self, mock_get, mock_dns):
        """URL should be validated before making request."""
        # Mock DNS to return public IP
        mock_dns.return_value = [(2, 1, 0, '', ('93.184.216.34', 80))]
        mock_get.return_value = MagicMock(status_code=200)
        
        client = SafeHTTPClient()
        response = client.get('https://example.com/')
        
        assert mock_get.called
    
    @patch('socket.getaddrinfo')
    def test_blocked_url_no_request(self, mock_dns):
        """Blocked URLs should not make network requests."""
        # Mock DNS to return private IP
        mock_dns.return_value = [(2, 1, 0, '', ('127.0.0.1', 80))]
        
        client = SafeHTTPClient()
        
        with pytest.raises(SSRFError):
            client.get('http://localhost/')
