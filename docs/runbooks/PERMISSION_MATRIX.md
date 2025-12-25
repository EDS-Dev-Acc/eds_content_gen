# Permission Matrix

## Overview

EMCIP uses role-based access control with three primary roles:

| Role | Description |
|------|-------------|
| **Viewer** | Read-only access to data |
| **Operator** | Full CRUD operations, run crawls |
| **Admin** | All permissions + destructive actions |

## Permission Classes

Located in `apps/core/permissions.py`:

| Class | Description |
|-------|-------------|
| `IsViewer` | Requires viewer role or higher |
| `IsOperator` | Requires operator role or higher |
| `IsAdmin` | Requires admin role |
| `DestructiveActionPermission` | Required for delete/bulk-delete operations |

## Endpoint Permission Matrix

### Seeds API (`/api/seeds/`)

| Action | Endpoint | Permission | Throttle |
|--------|----------|------------|----------|
| List | `GET /api/seeds/` | IsAuthenticated | - |
| Detail | `GET /api/seeds/{id}/` | IsAuthenticated | - |
| Create | `POST /api/seeds/` | IsAuthenticated | - |
| Update | `PUT/PATCH /api/seeds/{id}/` | IsAuthenticated | - |
| Delete | `DELETE /api/seeds/{id}/` | IsAuthenticated + DestructiveAction | - |
| Bulk Import | `POST /api/seeds/import/` | IsAuthenticated | 20/min |
| Validate | `POST /api/seeds/{id}/validate/` | IsAuthenticated | 10/min (probe) |
| Discover | `POST /api/seeds/{id}/discover-entrypoints/` | IsAuthenticated | 10/min (discovery) |
| Test Crawl | `POST /api/seeds/{id}/test-crawl/` | IsAuthenticated | 10/min (probe) |
| Promote | `POST /api/seeds/{id}/promote/` | IsAuthenticated | - |
| Batch Promote | `POST /api/seeds/batch-promote/` | IsAuthenticated | 10/min (bulk) |

### Sources API (`/api/sources/`)

| Action | Endpoint | Permission | Throttle |
|--------|----------|------------|----------|
| List | `GET /api/sources/` | IsAuthenticated | - |
| Detail | `GET /api/sources/{id}/` | IsAuthenticated | - |
| Create | `POST /api/sources/` | IsAuthenticated | - |
| Update | `PUT/PATCH /api/sources/{id}/` | IsAuthenticated | - |
| Delete | `DELETE /api/sources/{id}/` | IsAuthenticated + DestructiveAction | - |
| Test | `POST /api/sources/{id}/test/` | IsAuthenticated | 10/min (probe) |
| Crawl Now | `POST /api/sources/{id}/crawl-now/` | IsAuthenticated | 5/min (crawl) |

### Runs API (`/api/runs/`)

| Action | Endpoint | Permission | Throttle |
|--------|----------|------------|----------|
| List | `GET /api/runs/` | IsAuthenticated | - |
| Detail | `GET /api/runs/{id}/` | IsAuthenticated | - |
| Start | `POST /api/runs/` | IsAuthenticated | 5/min (crawl) |
| Cancel | `POST /api/runs/{id}/cancel/` | IsAuthenticated | - |
| Delete | `DELETE /api/runs/{id}/` | IsAdmin | - |

### Schedules API (`/api/schedules/`)

| Action | Endpoint | Permission | Throttle |
|--------|----------|------------|----------|
| List | `GET /api/schedules/` | IsAuthenticated | - |
| Detail | `GET /api/schedules/{id}/` | IsAuthenticated | - |
| Create | `POST /api/schedules/` | IsOperator | - |
| Update | `PUT/PATCH /api/schedules/{id}/` | IsOperator | - |
| Delete | `DELETE /api/schedules/{id}/` | IsAdmin + DestructiveAction | - |
| Toggle | `POST /api/schedules/{id}/toggle/` | IsOperator | - |
| Run Now | `POST /api/schedules/{id}/run-now/` | IsOperator | 5/min (crawl) |
| Pause All | `POST /api/schedules/pause-all/` | IsAdmin | 10/min (bulk) |
| Bulk Delete | `POST /api/schedules/bulk-delete/` | IsAdmin + DestructiveAction | 10/min (bulk) |

### Articles API (`/api/articles/`)

| Action | Endpoint | Permission | Throttle |
|--------|----------|------------|----------|
| List | `GET /api/articles/` | IsAuthenticated | - |
| Detail | `GET /api/articles/{id}/` | IsAuthenticated | - |
| Bulk Action | `POST /api/articles/bulk/` | IsAuthenticated (delete requires DestructiveAction) | 10/min (bulk) |
| Export | `GET /api/articles/export/` | IsAuthenticated | 5/min (export) |

### Exports API (`/api/exports/`)

| Action | Endpoint | Permission | Throttle |
|--------|----------|------------|----------|
| List | `GET /api/exports/` | IsAuthenticated | - |
| Create | `POST /api/exports/` | IsAuthenticated | 5/min (export) |
| Detail | `GET /api/exports/{id}/` | IsAuthenticated | - |
| Download | `GET /api/exports/{id}/download/` | IsAuthenticated | - |
| Delete | `DELETE /api/exports/{id}/` | IsAuthenticated | - |

## Throttle Rate Summary

| Scope | Rate | Endpoints |
|-------|------|-----------|
| `probe` | 10/minute | validate, test-crawl, source test |
| `discovery` | 10/minute | discover-entrypoints |
| `crawl` | 5/minute | runs, crawl-now, run-now |
| `import` | 20/minute | seed import |
| `export` | 5/minute | article export |
| `bulk_action` | 10/minute | bulk operations |
| `burst` | 100/minute | General rate limit |
| `daily` | 1000/day | Expensive operations |

## Configuration

### Custom Throttle Rates

Override in `settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'probe': '20/minute',
        'discovery': '15/minute',
        'crawl': '10/minute',
        'import': '30/minute',
        'export': '10/minute',
        'bulk_action': '15/minute',
    }
}
```

### User Role Assignment

```python
from apps.core.models import OperatorProfile

profile = OperatorProfile.objects.get(user=user)
profile.role = 'admin'  # viewer, operator, admin
profile.save()
```

## Related

- [apps/core/permissions.py](../../apps/core/permissions.py)
- [apps/core/throttling.py](../../apps/core/throttling.py)
