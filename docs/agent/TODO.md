# Operator Console MVP - Task Checklist

## Legend
- [ ] Not started
- [~] In progress
- [x] Complete
- [!] Blocked

---

## Phase 14.1: Pre-Tagging Readiness Audit
- [x] Verify orchestration lifecycle (atomic aggregation, cancellation)
- [x] Verify seeds import on_duplicate modes
- [x] Verify seeds validate/discover/test-crawl response completeness
- [x] Verify sources test/crawl-now SSRF protection
- [x] Add HTTPFetcher SSRF protection
- [x] Apply throttle classes to endpoints
- [x] Add CrawlJob date filter indexes
- [x] Update GAP_ANALYSIS.md with verified status

---

## Phase 15: Production Deployment
- [x] Create Dockerfile with multi-stage build
- [x] Create docker-compose.prod.yml
- [x] Configure Nginx reverse proxy
- [x] Set up OpenTelemetry tracing
- [x] Add Jaeger, Prometheus, Grafana profiles
- [x] Configure production settings

---

## Phase 14: API Improvements
- [x] Seeds update_fields merge with diffs
- [x] ExportJob async flow
- [x] Orchestration fixes
- [x] DRF SafeDefaultRouter fix
- [x] Metrics instrumentation
- [x] Request ID middleware

---

## Phase 10.0: Recon + Baseline
- [x] Create /docs/agent/ directory
- [x] Read existing models (Source, Article, CrawlJob)
- [x] Document existing API endpoints
- [x] Create STATE.md
- [x] Create TODO.md
- [x] Create ENDPOINTS.md
- [x] Create SCHEMA.md
- [x] Create TESTING.md
- [x] Create CHANGELOG.md
- [x] Create SESSION_LOG.md
- [x] Verify existing tests pass (30/30)

---

## Phase 10.1: JWT Auth Foundation
- [x] Install djangorestframework-simplejwt
- [x] Configure JWT settings in base.py
- [x] Create OperatorProfile model
- [x] Create migration for OperatorProfile
- [x] Add /api/auth/login/ endpoint (TokenObtainPairView)
- [x] Add /api/auth/refresh/ endpoint (TokenRefreshView)
- [x] Add /api/auth/me/ endpoint (current user info)
- [x] Add /api/auth/logout/ endpoint (token blacklist)
- [x] Update DRF DEFAULT_AUTHENTICATION_CLASSES
- [x] Write auth tests (10/10)
- [x] Commit changes

---

## Phase 10.2: Runs API + History
- [x] Extend CrawlJob model (config_overrides, priority, triggered_by)
- [x] Create CrawlJobSourceResult model
- [x] Create migration
- [x] Create RunSerializer
- [x] Create /api/runs/ endpoints
- [x] Write Runs API tests (15/15)
- [x] Commit changes

---

## Phase 10.3: Schedules API + django-celery-beat
- [x] Install django-celery-beat
- [x] Add to INSTALLED_APPS
- [x] Run django-celery-beat migrations
- [x] Create ScheduleSerializer
- [x] Create /api/schedules/ CRUD endpoints
- [x] Write Schedule API tests (15/15)
- [x] Commit changes

---

## Phase 10.4: Seeds App + Promote Wizard
- [x] Create apps/seeds app
- [x] Create Seed model
- [x] Create SeedBatch model
- [x] Create migration
- [x] Create SeedSerializer
- [x] Create /api/seeds/ CRUD endpoints
- [x] Create /api/seeds/import/ bulk import
- [x] Create /api/seeds/{id}/validate/ endpoint
- [x] Create /api/seeds/{id}/promote/ endpoint
- [x] Write Seeds API tests (18/18)
- [x] Commit changes

---

## Phase 10.5: Article Viewer (7-tab)
- [x] Create ArticleRawCapture model
- [x] Create ArticleScoring model
- [x] Create ArticleLLMArtifact model
- [x] Create ArticleImage model
- [x] Create migrations
- [x] Create ArticleDetailSerializer
- [x] Create /api/articles/ endpoints with tabs
- [x] Write Article API tests
- [x] Commit changes

---

## Phase 10.6: LLM Settings + Budgets
- [x] Create LLMSettings model
- [x] Create migration
- [x] Create LLMSettingsSerializer
- [x] Create /api/settings/llm/ endpoints
- [x] Add budget enforcement
- [x] Write LLM Settings tests
- [x] Commit changes

---

## Phase 10.7: HTMX Templates
- [x] Create base.html template
- [x] Create navigation component
- [x] Create dashboard template
- [x] Create sources/runs templates
- [x] Create schedules template
- [x] Create seeds template
- [x] Create articles templates
- [x] Create LLM settings template
- [x] Commit changes

---

## Phase 11.1: API Gap Analysis Fixes
- [x] SSRFGuard, URLNormalizer, SafeHTTPClient
- [x] ErrorCode enum with 35+ codes
- [x] Seeds enhancements (filters, discover, test-crawl)
- [x] Sources full CRUD with test/crawl-now
- [x] Runs POST alias and date filters
- [x] Articles filters and actions
- [x] Commit changes

---

## Phase 12-13: Content Generation
- [x] ContentOpportunity model
- [x] OpportunityFinder service
- [x] DraftGenerator service
- [x] Content API endpoints
- [x] Celery tasks
- [x] Commit changes

---

## Next: Semantic Tagging Layer
- [ ] Design tag taxonomy model
- [ ] Implement auto-tagging pipeline
- [ ] Create tag management API
- [ ] Integrate with article processing

---

## Notes
- All API endpoints require JWT auth (except login/refresh)
- Pre-tagging audit complete - ready for tagging layer
- All 15 phases complete through Phase 14.1
