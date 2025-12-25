# EMCIP Gap Analysis & Action Plan

**Last Updated**: December 2025 (Phase 14.1 Audit Complete)  
**Status**: All Core Items Complete - Pre-Tagging Ready

---

## Executive Summary

This document tracks gaps between the current implementation and the target frontend/API contract, along with prioritized fixes.

### Legend
- ✅ **Done** - Already implemented
- 🔧 **Needs Fix** - Exists but needs improvement
- ❌ **Missing** - Not yet implemented
- ⏳ **In Progress** - Currently being worked on

---

## A) Seeds Endpoints & UX Parity

### Import Endpoint (`POST /api/seeds/import/`)

| Item | Status | Notes |
|------|--------|-------|
| Bulk URL import | ✅ Done | Works with urls, csv, opml formats |
| Duplicate detection | ✅ Done | Uses `normalized_url` for dedupe |
| `on_duplicate` strategies | ✅ Done | Supports `skip`, `update`, `error` |
| Return duplicate metadata | ✅ Done | Shows merged tags if updating |

**Status**: ✅ Complete (Session 23)

### Validate Endpoint (`POST /api/seeds/{id}/validate/`)

| Item | Status | Notes |
|------|--------|-------|
| SSRF protection | ✅ Done | SafeHTTPClient with SSRF guard |
| Basic reachability | ✅ Done | Returns is_reachable |
| `final_url` detection | ✅ Done | Tracks redirect destination |
| `content_type` detection | ✅ Done | Detects MIME type from headers |
| `warnings` array | ✅ Done | For non-fatal issues (redirects, robots restrictions) |
| `detected.type_hint` | ✅ Done | Guesses seed type (news, blog, rss, sitemap) |
| `detected.feed_urls` | ✅ Done | Discovers RSS/Atom feeds |
| `detected.sitemap_url` | ✅ Done | Discovers sitemap |

**Status**: ✅ Complete (Session 23)

### Discover Entrypoints (`POST /api/seeds/{id}/discover-entrypoints/`)

| Item | Status | Notes |
|------|--------|-------|
| RSS/Atom feed detection | ✅ Done | Finds feed URLs with type detection |
| Sitemap detection | ✅ Done | Parses sitemap.xml with type metadata |
| Main page scanning | ✅ Done | Scans for links |
| URL normalization | ✅ Done | Uses URLNormalizer for all discovered URLs |
| Off-origin filtering | ✅ Done | Filters to same domain only |
| Type-specific metadata | ✅ Done | feed_type (rss/atom), sitemap_type |
| De-duplication | ✅ Done | Uses normalized_url for dedupe |

**Status**: ✅ Complete (Session 23)

### Test Crawl (`POST /api/seeds/{id}/test-crawl/`)

| Item | Status | Notes |
|------|--------|-------|
| Sample article extraction | ✅ Done | Returns sample content |
| `entrypoint_url` parameter | ✅ Done | Override crawl URL (same domain) |
| `max_pages` parameter | ✅ Done | Limit pages fetched (max 20) |
| `max_articles` parameter | ✅ Done | Limit articles extracted (max 10) |
| `stats.pages_fetched` | ✅ Done | In response |
| `stats.links_found` | ✅ Done | In response |
| Server-side caps | ✅ Done | max_pages=20, max_articles=10 |

**Status**: ✅ Complete (Session 23)

---

## B) Sources/Runs/Schedules Parity

### Sources Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/sources/` | ✅ Done | List with filters |
| `POST /api/sources/` | ✅ Done | Create source |
| `GET /api/sources/{id}/` | ✅ Done | Detail view |
| `PATCH /api/sources/{id}/` | ✅ Done | Update source |
| `DELETE /api/sources/{id}/` | ✅ Done | Delete source |
| `POST /api/sources/{id}/test/` | ✅ Done | Test connectivity |
| `POST /api/sources/{id}/crawl-now/` | ✅ Done | Trigger crawl |
| `GET /api/sources/stats/` | ✅ Done | Aggregate stats |

**Status**: ✅ Complete (implemented in Phase 11.1)

### Runs Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/runs/` | ✅ Done | List with filters |
| `POST /api/runs/` | ✅ Done | Alias for start (Phase 11.1) |
| `POST /api/runs/start/` | ✅ Done | Original endpoint |
| `GET /api/runs/{id}/` | ✅ Done | Run detail |
| `POST /api/runs/{id}/cancel/` | ✅ Done | Cancel run |
| `started_after/before` filters | ✅ Done | Date range filters |
| `completed_after/before` filters | ✅ Done | Date range filters |
| `totals` in list response | ✅ Done | Includes articles/errors/pages/status counts |

**Status**: ✅ Complete (Session 23)

### CrawlJob Orchestration

| Item | Status | Notes |
|------|--------|-------|
| Update CrawlJobSourceResult | ✅ Done | Worker updates correctly (Session 24) |
| Aggregate totals on completion | ✅ Done | Parent job sums child results |
| Set parent status to completed/failed | ✅ Done | Based on child statuses |
| Honor cancellation | ✅ Done | Stops running tasks (Session 24) |

**Status**: ✅ Complete (Session 24)

### Schedules Endpoints

| Item | Status | Notes |
|------|--------|-------|
| List/Create/Update/Delete | ✅ Done | CRUD works |
| Selection/params parsing | ✅ Done | Parsed from kwargs |
| `timezone` field | ✅ Done | Exposed in responses |
| `next_run_at` computed | ✅ Done | Calculated for interval schedules |
| Pause All semantics | ✅ Done | Bulk action exists |

**Status**: ✅ Complete (Session 23)

---

## C) Articles API

### Filters

| Filter | Status | Notes |
|--------|--------|-------|
| `status` | ✅ Done | processing_status filter |
| `source` / `source_id` | ✅ Done | Both aliases work |
| `quality` (high/medium/low) | ✅ Done | Score ranges |
| `score_gte` / `score_lte` | ✅ Done | Range filters |
| `region` | ✅ Done | primary_region filter |
| `topic` | ✅ Done | primary_topic filter |
| `language` | ✅ Done | Added in Phase 11.1 |
| `has_images` | ✅ Done | Added in Phase 11.1 |
| `has_citations` | ✅ Done | Added in Phase 11.1 |
| `has_statistics` | ✅ Done | Added in Phase 11.1 |
| `llm_touched` | ✅ Done | Filter by LLM processing |
| `ordering` | ✅ Done | Sort param |
| Date range filters | ✅ Done | collected/published after/before |

**Status**: ✅ Complete (Session 23)

### Actions

| Action | Status | Notes |
|--------|--------|-------|
| `POST /{id}/reprocess/` | ✅ Done | Triggers reprocessing |
| `POST /{id}/mark-used/` | ✅ Done | Marks as used |
| `POST /{id}/mark-ignored/` | ✅ Done | Marks as ignored |
| `POST /bulk/` | ✅ Done | Bulk actions |
| `GET /export/` | ✅ Done | CSV/JSON export |
| ExportJob model | ✅ Done | Async export tracking (Session 24) |

**Status**: ✅ Complete (Session 24)

### Payload Sizing

| Item | Status | Notes |
|------|--------|-------|
| Raw HTML handling | ✅ Done | Separate `/content/` endpoint |
| Lazy loading | ✅ Done | `?include_content=false` default in detail |
| Export streaming | ✅ Done | ExportJob async flow with file storage |
| Signed URLs | ⏳ Deferred | Nice-to-have for very large files |

**Status**: ✅ Core Complete (Session 24+26)

---

## D) Security & Correctness

### Normalization

| Item | Status | Notes |
|------|--------|-------|
| Seeds import normalization | ✅ Done | Uses URLNormalizer for dedupe (Session 23) |
| Discover entrypoints normalization | ✅ Done | URLNormalizer + same-domain filter |
| Test-crawl normalization | ✅ Done | URLNormalizer + same-domain validation |
| HTTPFetcher SSRF check | ✅ Done | Added validate_url_ssrf (Session 26) |

**Status**: ✅ Complete (Session 26)

### Robots.txt Parsing

| Item | Status | Notes |
|------|--------|-------|
| Fetch robots.txt | ✅ Done | Uses SafeHTTPClient |
| Parse rules | ✅ Done | RobotFileParser |
| Fallback on failure | ✅ Done | Adds warning, includes error message (Session 24) |

**Status**: ✅ Complete (Session 24)

### Permissions/Roles

| Item | Status | Notes |
|------|--------|-------|
| IsAuthenticated enforcement | ✅ Done | All views require auth |
| Role-based permissions | ✅ Done | IsViewer, IsOperator, IsAdmin classes |
| Destructive endpoint protection | ✅ Done | DestructiveActionPermission class |

**Status**: ✅ Complete (Session 23) - See `apps/core/permissions.py`

### Idempotency

| Item | Status | Notes |
|------|--------|-------|
| Promote idempotency | ✅ Done | Returns 409 with existing_source_id |
| Seed create idempotency | ✅ Done | Uses normalized_url for duplicate detection |

**Status**: ✅ Complete

---

## E) Observability

### Request ID Middleware

| Item | Status | Notes |
|------|--------|-------|
| Generate request_id per request | ✅ Done | UUID-based |
| Inject into logger | ✅ Done | RequestIDFilter class |
| Return in error responses | ✅ Done | X-Request-ID header |
| Pass to Celery tasks | ✅ Done | celery_request_id_headers() helper |

**Status**: ✅ Complete (Session 23) - See `apps/core/middleware.py`

### Prometheus Metrics

| Metric | Status | Notes |
|--------|--------|-------|
| `/metrics` endpoint | ✅ Done | metrics_view function |
| `seeds_import_total{status}` | ✅ Done | Counter with status/format labels |
| `seeds_validate_duration_ms` | ✅ Done | Histogram |
| `seeds_discover_entrypoints_total` | ✅ Done | Counter |
| `runs_started_total` | ✅ Done | Counter with trigger label |
| `runs_completed_total` | ✅ Done | Counter with status label |
| `schedules_trigger_total` | ✅ Done | Counter |
| `llm_token_usage_total` | ✅ Done | Counter with provider/model/type labels |
| `articles_processed_total` | ✅ Done | Counter |
| `http_requests_total` | ✅ Done | Counter with domain/status labels |

**Status**: ✅ Complete (Session 23) - See `apps/core/metrics.py`

### Tracing

| Item | Status | Notes |
|------|--------|-------|
| OpenTelemetry setup | ✅ Done | apps/core/tracing.py with graceful fallback |
| Endpoint tracing | ✅ Done | Trace IDs propagated via middleware |
| Celery task tracing | ✅ Done | celery_request_id_headers helper |

**Status**: ✅ Complete (Session 24) - Libraries optional, tracing auto-enabled when installed

---

## F) Performance & Scalability

### Rate Limiting

| Item | Status | Notes |
|------|--------|-------|
| DRF throttling | ✅ Done | Throttle classes created |
| Probe endpoint throttle | ✅ Done | 10/minute for validate/test-crawl |
| Crawl endpoint throttle | ✅ Done | 5/minute for run triggers |
| Import endpoint throttle | ✅ Done | 20/minute for bulk imports |

**Status**: ✅ Complete (Session 23) - See `apps/core/throttling.py`

### Content Parsing Caps

| Item | Status | Notes |
|------|--------|-------|
| Max pages per test-crawl | ✅ Done | Capped at 20 pages |
| Max articles per test-crawl | ✅ Done | Capped at 10 articles |
| Max links per discovery | ✅ Done | Capped at 100 links |

**Status**: ✅ Complete (Session 23)

---

## Prioritized Action Plan

### Priority 1: Critical for Frontend Parity ✅ COMPLETE

1. **Seeds Import Normalization** ✅
   - Use `normalized_url` for duplicate detection
   - Add `on_duplicate` strategy parameter (`skip`, `update`, `error`)
   - File: `apps/seeds/views.py` - `SeedBulkImportView`

2. **Validate Endpoint Enhancement** ✅
   - Add `final_url`, `content_type`, `warnings`, `detected.type_hint`
   - Add `detected.feed_urls`, `detected.sitemap_url`
   - File: `apps/seeds/views.py` - `SeedValidateView`

3. **Test-Crawl Parameters** ✅
   - Accept `entrypoint_url`, `max_pages`, `max_articles`
   - Add server-side caps (max_pages=20, max_articles=10)
   - File: `apps/seeds/views.py` - `SeedTestCrawlView`

4. **Runs List Totals** ✅
   - Include `totals` object in list responses
   - Aggregate stats: total_runs, articles, errors, pages, by_status
   - File: `apps/sources/views.py` - `RunViewSet.list()`

### Priority 2: Important for UX ✅ COMPLETE

5. **Discover Entrypoints Cleanup** ✅
   - Normalize and dedupe discovered URLs
   - Filter to same domain
   - Add feed_type, sitemap_type metadata
   - File: `apps/seeds/views.py` - `SeedDiscoverEntrypointsView`

6. **Schedule Serializer Enhancement** ✅
   - Parse kwargs to selection/params
   - Add timezone, next_run_at
   - File: `apps/sources/serializers.py`

7. **Articles `llm_touched` Filter** ✅
   - Filter by presence of LLM artifacts
   - File: `apps/articles/views.py`

### Priority 3: Security Hardening ✅ COMPLETE

8. **Role-Based Permissions** ✅
   - Create permission classes for roles (IsViewer, IsOperator, IsAdmin)
   - Apply to destructive endpoints (DestructiveActionPermission)
   - File: `apps/core/permissions.py` (new)

9. **Rate Limiting** ✅
   - Add throttle classes for probing endpoints
   - Scopes: probe, discovery, crawl, import, export
   - File: `apps/core/throttling.py` (new)

### Priority 4: Observability ✅ COMPLETE

10. **Request ID Middleware** ✅
    - Generate and propagate request IDs
    - RequestIDFilter for logging
    - Celery correlation support
    - File: `apps/core/middleware.py` (new)

11. **Prometheus Metrics** ✅
    - Add counters and histograms for all major operations
    - Seeds, runs, articles, LLM, HTTP metrics
    - File: `apps/core/metrics.py` (new)

---

## Implementation Status

| Item | Status | Completed Date |
|------|--------|----------------|
| Seeds Import Normalization | ✅ Done | Session 23 |
| Validate Endpoint Enhancement | ✅ Done | Session 23 |
| Test-Crawl Parameters | ✅ Done | Session 23 |
| Runs List Totals | ✅ Done | Session 23 |
| Discover Entrypoints Cleanup | ✅ Done | Session 23 |
| Schedule Enhancement | ✅ Done | Session 23 |
| Articles llm_touched | ✅ Done | Session 23 |
| Role-Based Permissions | ✅ Done | Session 23 |
| Rate Limiting | ✅ Done | Session 23 |
| Request ID Middleware | ✅ Done | Session 23 |
| Prometheus Metrics | ✅ Done | Session 23 |
| Seeds update_fields merge | ✅ Done | Session 24 |
| CrawlJob cancellation handling | ✅ Done | Session 24 |
| ExportJob async exports | ✅ Done | Session 24 |
| Export metrics | ✅ Done | Session 24 |
| DRF router fix | ✅ Done | Session 24 |
| HTTPFetcher SSRF protection | ✅ Done | Session 26 |
| Throttle classes applied to views | ✅ Done | Session 26 |
| CrawlJob date filter indexes | ✅ Done | Session 26 |
| Payload lazy loading verified | ✅ Done | Session 26 |

---

## Session 26 Audit Summary

### Verified Working
1. **Orchestration lifecycle** - `_finalize_parent_job` uses atomic transaction, proper status aggregation
2. **Seeds import** - URLNormalizer, on_duplicate modes, merged_fields tracking
3. **Seeds validate/discover/test-crawl** - All response fields present, server-side caps enforced
4. **Sources test/crawl-now** - SafeHTTPClient, status checks, task_id returned
5. **Request ID** - `RequestIDMiddleware` in settings, propagated to Celery
6. **Runs list totals** - Aggregates with by_status counts, date filters working

### Gaps Fixed
| Gap | Fix |
|-----|-----|
| HTTPFetcher missing SSRF | Added `validate_url_ssrf()` check |
| Throttle classes not applied | Applied to 7 endpoint views |
| Missing date indexes | Created migration 0006_crawljob_date_indexes |

---

## Notes

### Strengths to Retain
- SSRFGuard and SafeHTTPClient are well-structured
- `normalized_url` constraint is valuable for dedupe
- ErrorCode taxonomy gives frontend reliable error handling
- Seeds discover/test-crawl endpoints are actionable

### Dependencies
- Frontend wizard expects specific response shapes
- Celery beat integration for schedule timing
- Prometheus client library for metrics
 