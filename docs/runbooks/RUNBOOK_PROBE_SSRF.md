# Runbook: Probe Rate Spikes and SSRF Handling

## Overview

This runbook covers handling high probe request rates (validation, discovery, test-crawl) and SSRF-related issues.

## Symptoms

### Rate Spike Indicators
- 429 Too Many Requests responses from probe endpoints
- High CPU/memory on web workers
- Many concurrent external HTTP requests

### SSRF Indicators
- Logs containing `SSRF_BLOCKED` error codes
- Requests to internal IPs (10.x, 172.16.x, 192.168.x)
- Requests to metadata endpoints (169.254.169.254)

## Probe Endpoint Rate Limits

| Endpoint | Throttle Class | Default Rate |
|----------|---------------|--------------|
| `/api/seeds/{id}/validate/` | ProbeEndpointThrottle | 10/minute |
| `/api/seeds/{id}/discover-entrypoints/` | DiscoveryEndpointThrottle | 10/minute |
| `/api/seeds/{id}/test-crawl/` | ProbeEndpointThrottle | 10/minute |
| `/api/seeds/import/` | ImportEndpointThrottle | 20/minute |

## Diagnosis Steps

### 1. Check Current Rate Usage

```python
# In Django shell
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='<username>')

# Check throttle keys
key = f"throttle_probe_{user.pk}"
print(cache.get(key))
```

### 2. Check for Abuse Patterns

```sql
-- Recent probe requests by user (if logging is enabled)
SELECT user_id, COUNT(*), MIN(created_at), MAX(created_at)
FROM request_log
WHERE path LIKE '%/validate%' OR path LIKE '%/discover%' OR path LIKE '%/test-crawl%'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY user_id
ORDER BY COUNT(*) DESC;
```

### 3. Check SSRF Block Logs

```bash
# Search for SSRF blocks
grep "SSRF" /var/log/django/app.log | tail -50
grep "SSRF_BLOCKED" /var/log/django/app.log | tail -50
```

## Resolution Steps

### For Rate Limit Abuse

1. **Temporarily block user**:
   ```python
   from django.contrib.auth import get_user_model
   User = get_user_model()
   user = User.objects.get(username='<abuser>')
   user.is_active = False
   user.save()
   ```

2. **Clear throttle cache** (for legitimate users hitting limits):
   ```python
   from django.core.cache import cache
   # Clear specific user's throttle
   cache.delete(f"throttle_probe_{user.pk}")
   cache.delete(f"throttle_discovery_{user.pk}")
   ```

3. **Adjust rates if too restrictive** (in settings):
   ```python
   REST_FRAMEWORK = {
       'DEFAULT_THROTTLE_RATES': {
           'probe': '20/minute',  # Increase from 10
           'discovery': '15/minute',
       }
   }
   ```

### For SSRF False Positives

If a legitimate external URL is being blocked:

1. **Verify the URL** - Check why it's being blocked:
   ```python
   from apps.core.security import SSRFGuard, URLNormalizer
   
   url = 'https://example.com/path'
   guard = SSRFGuard()
   try:
       guard.validate(url)
       print("URL is safe")
   except Exception as e:
       print(f"Blocked: {e}")
   ```

2. **Check IP resolution**:
   ```python
   import socket
   hostname = 'example.com'
   ip = socket.gethostbyname(hostname)
   print(f"{hostname} resolves to {ip}")
   ```

3. **Add to allowlist** (if truly safe and necessary):
   ```python
   # In apps/core/security.py, SSRFGuard class
   ALLOWLISTED_HOSTS = ['safe-internal.company.com']
   ```

### For High Memory/CPU from Probes

1. **Check current probe limits**:
   ```python
   # In apps/seeds/views.py
   # SeedDiscoverEntrypointsView
   MAX_LINKS_PER_PAGE = 100
   MAX_TOTAL_ENTRYPOINTS = 50
   
   # SeedTestCrawlView
   MAX_PAGES = 20
   MAX_LINKS_PER_PAGE = 100
   ```

2. **Reduce limits if needed** by editing these class constants

## Prevention

### Throttle Configuration

Ensure throttle rates are configured in settings:

```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'probe': '10/minute',
        'discovery': '10/minute',
        'crawl': '5/minute',
        'import': '20/minute',
        'export': '5/minute',
        'bulk_action': '10/minute',
    }
}
```

### SSRF Protection

The `SSRFGuard` blocks:
- Private IP ranges (10.x, 172.16-31.x, 192.168.x)
- Loopback (127.x)
- Link-local (169.254.x)
- Cloud metadata (169.254.169.254)
- Blocked ports (22, 23, 25, etc.)

## Monitoring

Alert on:
- More than 100 probe requests per user per hour
- Any SSRF_BLOCKED events (may indicate malicious activity)
- 429 responses exceeding 50/hour

## Related

- [apps/core/security.py](../../apps/core/security.py) - SSRFGuard, SafeHTTPClient
- [apps/core/throttling.py](../../apps/core/throttling.py) - Throttle classes
- [apps/seeds/views.py](../../apps/seeds/views.py) - Probe endpoints
