"""
Rate Limiting / Throttling for EMCIP.

Custom DRF throttle classes for different endpoint types.

Usage in views:
    from apps.core.throttling import ProbeEndpointThrottle, CrawlEndpointThrottle
    
    class SeedValidateView(APIView):
        throttle_classes = [ProbeEndpointThrottle]

Usage in settings:
    REST_FRAMEWORK = {
        'DEFAULT_THROTTLE_RATES': {
            'probe': '10/minute',      # URL validation, test crawl
            'crawl': '5/minute',       # Trigger crawl operations
            'import': '20/minute',     # Bulk imports
            'export': '5/minute',      # Data exports
            'discovery': '10/minute',  # Entrypoint discovery
        }
    }
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
import logging

logger = logging.getLogger(__name__)


class ProbeEndpointThrottle(UserRateThrottle):
    """
    Throttle for probing endpoints that make external HTTP requests.
    
    Applies to:
    - POST /api/seeds/{id}/validate/
    - POST /api/seeds/{id}/test-crawl/
    - POST /api/sources/{id}/test/
    
    Default: 10 requests/minute
    """
    scope = 'probe'
    
    def get_rate(self):
        """Get rate from settings or use default."""
        try:
            return super().get_rate()
        except Exception:
            return '10/minute'


class DiscoveryEndpointThrottle(UserRateThrottle):
    """
    Throttle for discovery endpoints that scan external sites.
    
    Applies to:
    - POST /api/seeds/{id}/discover-entrypoints/
    
    Default: 10 requests/minute
    """
    scope = 'discovery'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '10/minute'


class CrawlEndpointThrottle(UserRateThrottle):
    """
    Throttle for endpoints that trigger crawl jobs.
    
    Applies to:
    - POST /api/runs/start/
    - POST /api/runs/
    - POST /api/sources/{id}/crawl-now/
    
    Default: 5 requests/minute
    """
    scope = 'crawl'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '5/minute'


class ImportEndpointThrottle(UserRateThrottle):
    """
    Throttle for bulk import endpoints.
    
    Applies to:
    - POST /api/seeds/import/
    - POST /api/articles/bulk/
    
    Default: 20 requests/minute
    """
    scope = 'import'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '20/minute'


class ExportEndpointThrottle(UserRateThrottle):
    """
    Throttle for data export endpoints.
    
    Applies to:
    - GET /api/articles/export/
    - GET /api/seeds/export/
    
    Default: 5 requests/minute
    """
    scope = 'export'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '5/minute'


class BurstThrottle(UserRateThrottle):
    """
    Burst throttle to prevent rapid-fire requests.
    
    Allows short bursts but limits sustained high rates.
    
    Default: 100 requests/minute
    """
    scope = 'burst'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '100/minute'


class BulkActionThrottle(UserRateThrottle):
    """
    Throttle for bulk action endpoints.
    
    Applies to:
    - POST /api/articles/bulk/
    - POST /api/seeds/batch-promote/
    - POST /api/schedules/pause-all/
    
    Default: 10 requests/minute
    """
    scope = 'bulk_action'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '10/minute'


class DailyLimitThrottle(UserRateThrottle):
    """
    Daily limit throttle for expensive operations.
    
    Applies to operations that should have daily caps:
    - LLM processing requests
    - Large exports
    
    Default: 1000 requests/day
    """
    scope = 'daily'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '1000/day'


class AnonProbeThrottle(AnonRateThrottle):
    """
    Throttle for anonymous probe requests (if allowed).
    
    Much stricter than authenticated users.
    
    Default: 2 requests/minute
    """
    scope = 'anon_probe'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '2/minute'


class DestructiveActionThrottle(UserRateThrottle):
    """
    Throttle for destructive actions (DELETE, cancel, etc.).
    
    Phase 18: Added for hardening high-impact endpoints.
    
    Applies to:
    - DELETE on any resource
    - POST /api/runs/{id}/cancel/
    - POST /api/schedules/pause-all/
    
    Default: 20 requests/minute
    """
    scope = 'destructive'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '20/minute'


class StateChangeThrottle(UserRateThrottle):
    """
    Throttle for state-changing operations that aren't destructive.
    
    Phase 18: Added for hardening high-impact endpoints.
    
    Applies to:
    - POST /api/seeds/{id}/promote/
    - POST /api/seeds/batch-promote/
    - POST /api/articles/{id}/reprocess/
    
    Default: 30 requests/minute
    """
    scope = 'state_change'
    
    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return '30/minute'


# Default throttle rates to add to settings
DEFAULT_THROTTLE_RATES = {
    'probe': '10/minute',
    'discovery': '10/minute',
    'crawl': '5/minute',
    'import': '20/minute',
    'export': '5/minute',
    'bulk_action': '10/minute',
    'burst': '100/minute',
    'daily': '1000/day',
    'anon_probe': '2/minute',
}
