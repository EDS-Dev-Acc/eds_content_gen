# Operator Console MVP - Changelog

All notable changes to the Operator Console MVP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Phase 14.1 - Pre-Tagging Readiness Audit
**Status**: Complete ✅
**Date**: 2025-12-24

#### Added
- HTTPFetcher SSRF protection in `apps/sources/crawlers/fetchers/http_fetcher.py`
- Throttle classes applied to 7 endpoint views
- CrawlJob date filter indexes (started_at, completed_at)
- Migration `0006_crawljob_date_indexes.py`

#### Changed
- `apps/seeds/views.py` - Added throttle_classes to SeedBulkImportView, SeedValidateView, SeedDiscoverEntrypointsView, SeedTestCrawlView
- `apps/sources/views.py` - Added get_throttles() to RunViewSet and SourceViewSet
- `apps/articles/views.py` - Added throttle_classes to ArticleExportView
- `docs/GAP_ANALYSIS.md` - Updated all items to reflect verified status

#### Verified
- Orchestration lifecycle with atomic parent aggregation
- Seeds import on_duplicate modes (skip/update/error)
- Seeds validate/discover/test-crawl response completeness
- Sources test/crawl-now with SSRF protection
- Request ID middleware and Celery propagation
- Runs list totals and date range filters

---

### Phase 15 - Production Deployment
**Status**: Complete ✅
**Date**: 2025-12-23

#### Added
- Docker Compose production configuration
- OpenTelemetry tracing with OTLP exporter
- Nginx reverse proxy configuration
- Jaeger, Prometheus, Grafana observability profiles
- Production settings with security hardening

---

### Phase 14 - API Improvements
**Status**: Complete ✅
**Date**: 2025-12-23

#### Added
- Seeds merge with update_fields and merged_fields tracking
- ExportJob async flow for large exports
- Orchestration fixes for multi-source runs
- DRF SafeDefaultRouter for URL converter issue

---

### Phase 10.5 - Article Viewer (7 Tabs)
**Status**: Complete ✅

#### Added
- Created Article-related models in `apps/articles/models.py`:
  - `ArticleRawCapture` - HTTP capture metadata (status, headers, timing)
  - `ArticleScoreBreakdown` - Detailed scoring with reasoning
  - `ArticleLLMArtifact` - LLM prompt/response pairs
  - `ArticleImage` - Extracted images with metadata
- Created migration `0002_article_viewer_models`
- Created serializers in `apps/articles/serializers.py`:
  - `ArticleListSerializer` - Compact list view
  - `ArticleInfoSerializer` - Tab 1: Basic info
  - `ArticleRawCaptureTabSerializer` - Tab 2: Raw capture
  - `ArticleExtractedTextSerializer` - Tab 3: Extracted text
  - `ArticleScoresTabSerializer` - Tab 4: Score breakdown
  - `ArticleLLMArtifactsTabSerializer` - Tab 5: LLM artifacts
  - `ArticleImagesTabSerializer` - Tab 6: Images
  - `ArticleUsageSerializer` - Tab 7: Usage history
  - `ArticleDetailSerializer` - Full detail with relations
- Created views in `apps/articles/views.py`:
  - `ArticleViewSet` with 7 tab action endpoints
  - `ArticleLLMArtifactDetailView` - Individual artifact detail
  - `ArticleStatsView` - Aggregate statistics
- Added URL routes at `/api/articles/`
- List filters: status, source, quality, topic, region, ai_detected, used, search
- Created `apps/articles/tests.py` - 19 tests

#### Tests
- 19/19 article viewer tests passing

---

### Phase 10.4 - Seeds App
**Status**: Complete ✅

#### Added
- Created `apps/seeds` Django app
- Created `Seed` model with fields:
  - url, domain, status, validation_result
  - discovered_by, discovery_source, notes
  - promoted_at, promoted_to_source
- Created `SeedBatch` model for import tracking
- Created seed serializers
- Created seed views (CRUD + import/validate/promote)
- Added URL routes at `/api/seeds/`
- Created `scripts/test_seeds.py` - 18 tests

#### Tests
- 18/18 seeds tests passing

---

### Phase 10.3 - Schedules API + django-celery-beat
**Status**: Complete ✅

#### Added
- Installed `django-celery-beat` package for DB-backed scheduling
- Updated `CELERY_BEAT_SCHEDULER` to `DatabaseScheduler`
- Created schedule serializers:
  - `IntervalScheduleSerializer`
  - `CrontabScheduleSerializer`
  - `ScheduleListSerializer`
  - `ScheduleDetailSerializer`
  - `ScheduleCreateSerializer`
  - `ScheduleUpdateSerializer`
  - `ScheduleToggleSerializer`
  - `ScheduleRunNowSerializer`
  - `ScheduleBulkActionSerializer`
- Created schedule views:
  - `ScheduleViewSet` - CRUD for PeriodicTask
  - `ScheduleToggleView` - Toggle enabled state
  - `ScheduleRunNowView` - Trigger immediate run
  - `SchedulePauseAllView` - Pause/resume all schedules
  - `ScheduleBulkActionView` - Bulk enable/disable/delete
- Added schedule URL routes under `/api/sources/schedules/`
- Created `scripts/test_schedules_api.py` - 15 tests

#### Tests
- 15/15 schedule tests passing

---

### Phase 10.2 - Runs API + History
**Status**: Complete ✅

#### Added
- Extended `CrawlJob` model with:
  - `config_overrides` (JSONField)
  - `priority` (1-9, default 5)
  - `triggered_by` (manual/schedule/api)
  - `triggered_by_user` (FK to User)
  - `is_multi_source` (boolean)
  - `cancelled` status option
- Created `CrawlJobSourceResult` model for multi-source run tracking
- Created run serializers:
  - `SourceMinimalSerializer`
  - `CrawlJobSourceResultSerializer`
  - `CrawlJobListSerializer`
  - `CrawlJobDetailSerializer`
  - `RunStartSerializer`
  - `RunCancelSerializer`
- Created run views:
  - `RunViewSet` - List/retrieve runs
  - `RunStartView` - Start new runs
  - `RunCancelView` - Cancel running jobs
  - `SourceListView` - List sources for runs
- Added URL routes under `/api/sources/`
- Created `scripts/test_runs.py` - 15 tests
- Updated `crawl_source` task to support parent_job_id and config_overrides

#### Tests
- 15/15 runs tests passing

---

### Phase 10.1 - JWT Auth Foundation
**Status**: Complete ✅

#### Added
- Installed `djangorestframework-simplejwt` package
- Configured JWT settings in `base.py`:
  - 60-minute access token lifetime
  - 7-day refresh token lifetime
  - Token blacklist enabled
  - Custom claims (username, email, role)
- Created `OperatorProfile` model (1:1 with User)
- Added auto-creation signals for OperatorProfile
- Created auth serializers:
  - `UserSerializer`
  - `OperatorProfileSerializer`
  - `CustomTokenObtainPairSerializer`
  - `UserUpdateSerializer`
- Created auth views:
  - `CustomTokenObtainPairView` - Login with custom claims
  - `CustomTokenRefreshView` - Token refresh
  - `CurrentUserView` - GET/PATCH current user
  - `LogoutView` - Token blacklist
- Added URL routes under `/api/auth/`
- Created `scripts/test_auth.py` - 10 tests

#### Tests
- 10/10 auth tests passing

---

### Phase 10.0 - Recon + Baseline
**Status**: Complete ✅

#### Added
- Created `/docs/agent/` directory for state management
- Created `STATE.md` - Project state tracking
- Created `TODO.md` - Task checklist
- Created `ENDPOINTS.md` - API endpoint reference
- Created `SCHEMA.md` - Database schema reference
- Created `TESTING.md` - Testing guide
- Created `CHANGELOG.md` - This file
- Created `SESSION_LOG.md` - Session activity log

#### Documented
- Existing models: Source, CrawlJob, Article
- Existing endpoints: /api/content/*, /health/*, etc.
- Existing LLM infrastructure: ClaudeClient, PromptRegistry, CostTracker
- Key decisions from clarifying questions

#### Tests
- 30/30 existing integration tests verified passing

---

## [0.9.0] - Phase 9 Complete (Previous Session)

### Added
- Full integration testing (30/30 tests passing)
- All Phases 2-9 working together

### Summary of Phases 2-9
- **Phase 2**: Interface abstractions (Fetcher, LinkExtractor, Paginator ABCs)
- **Phase 3**: Pagination memory (Source.pagination_state)
- **Phase 4**: Playwright JS handling (PlaywrightFetcher, HybridFetcher)
- **Phase 5**: Extraction quality (TrafilaturaExtractor, HybridContentExtractor)
- **Phase 6**: Article processing state machine
- **Phase 7**: LLM hardening (prompts, tokens, caching, costs)
- **Phase 8**: Observability (logging, metrics, health checks)
- **Phase 9**: Final integration and cleanup

---

## Upcoming Phases

### Phase 10.4 - Seeds App + Promote Wizard
- [ ] Seeds app creation
- [ ] Seed model
- [ ] Import/validate/promote endpoints
- [ ] HTMX wizard

### Phase 10.5 - Article Viewer (7-tab)
- [ ] Article related models
- [ ] Enhanced detail endpoint
- [ ] 7-tab HTMX viewer

### Phase 10.6 - LLM Settings + Budgets
- [ ] LLMSettings model
- [ ] Settings API
- [ ] Budget enforcement

---

## Version History

| Version | Phase | Date | Status |
|---------|-------|------|--------|
| 0.9.0 | 9 | 2025-12-23 | Complete |
| 0.8.0 | 8 | - | Complete |
| 0.7.0 | 7 | - | Complete |
| 0.6.0 | 6 | - | Complete |
| 0.5.0 | 5 | - | Complete |
| 0.4.0 | 4 | - | Complete |
| 0.3.0 | 3 | - | Complete |
| 0.2.0 | 2 | - | Complete |
| 1.0.0 | 10.6 | TBD | Planned |
