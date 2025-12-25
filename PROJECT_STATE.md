# EMCIP Project State

## Last Updated
Date: 2025-12-24
Session: 31
Status: Phase 16 Verified & Enhanced - Discovery Architecture Complete

## Completed Features
- [x] Django project setup
- [x] Source model and admin
- [x] Article model and storage
- [x] Basic HTTP crawler (requests + BeautifulSoup)
- [x] Celery task queue with CrawlJob tracking
- [x] Text extraction (newspaper3k)
- [x] Translation (Google Translate fallback)
- [x] Article scoring pipeline
- [x] Claude API integration wrapper
- [x] Crawler pagination support (param, path, next-link)
- [x] Per-domain rate limiting
- [x] Async parallel article fetching (aiohttp)
- [x] URL normalization and deduplication
- [x] **Phase 2**: Interface abstractions (Fetcher, LinkExtractor, Paginator ABCs)
- [x] **Phase 3**: Pagination memory (persistence in Source model)
- [x] **Phase 4**: Playwright JS handling (PlaywrightFetcher, HybridFetcher)
- [x] **Phase 5**: Extraction quality (trafilatura + hybrid strategy)
- [x] **Phase 6**: State machine for article processing
- [x] **Phase 7**: LLM hardening (prompt templates, token counting, caching, cost tracking)
- [x] **Phase 8**: Observability (structured logging, metrics, health checks)
- [x] **Phase 9**: Final integration and cleanup (30/30 tests passing)
- [x] **Phase 10.1**: JWT Auth endpoints (login, logout, refresh, user)
- [x] **Phase 10.2**: Sources & Runs API (CRUD, crawl triggers, run history)
- [x] **Phase 10.3**: Schedule editor API (DB-backed schedules, interval/crontab)
- [x] **Phase 10.4**: Seeds manager API (Seed CRUD, categories, status, import)
- [x] **Phase 10.5**: Article viewer API (list, detail, filters, stats, reprocess)
- [x] **Phase 10.6**: LLM Settings & Budgets API (settings, usage, budget, models)
- [x] **Phase 10.7**: HTMX Templates (Operator Console UI)
- [x] **Phase 11.1**: API Gap Analysis Fixes (security, filters, endpoints)
- [x] **Phase 12**: Content Opportunity Finder (analyze articles, detect opportunities)
- [x] **Phase 13**: Content Synthesis (LLM-powered content generation)
- [x] **Phase 14**: API Improvements (seeds merge, exports, orchestration, observability)
- [x] **Phase 15**: Production Deployment (Docker, OpenTelemetry, performance)
- [x] **Phase 14.1**: Pre-Tagging Audit (SSRF fixes, throttling applied, date indexes)
- [x] **Phase 14.1 Refinements**: Error taxonomy, export URLs, query indexes
- [x] **Phase 16**: Seed Discovery Architecture (capture-first discovery, multi-channel connectors)

## Current Status
**🚀 PHASE 16 COMPLETE - SEED DISCOVERY ARCHITECTURE**

The platform now includes automated seed discovery with capture-first architecture:
- Multi-channel discovery connectors (SERP, RSS, HTML Directory, API)
- LLM-powered query generation with template fallback
- Raw HTTP capture storage with gzip compression
- Weighted multi-dimensional scoring
- Review workflow for human validation
- Console UI with HTMX partials
- CLI fallback for sync execution

### Phase 16 (Seed Discovery Architecture)
**New Models**:
| Model | Purpose |
|-------|---------|
| SeedRawCapture | Raw HTTP response capture with gzip compression |
| DiscoveryRun | Discovery session tracking with stats |
| Seed (extended) | +15 fields for provenance, scoring, review workflow |

**Discovery Pipeline** (`apps/seeds/discovery/`):
| Module | Purpose |
|--------|---------|
| connectors.py | BaseConnector, SERP, RSS, HTMLDirectory, API connectors |
| query_generator.py | LLM query expansion with template fallback |
| classifier.py | Page type classification |
| scoring.py | Weighted multi-factor scoring |
| tasks.py | Celery tasks with sync fallback |

**Console UI**:
| View | Purpose |
|------|---------|
| SeedsReviewQueueView | Main review queue page |
| SeedReviewActionView | Approve/reject individual seeds |
| SeedBulkReviewView | Bulk review actions |
| DiscoveryNewModalView | New discovery modal |
| SeedCapturePreviewView | Raw capture preview |

**CLI Command**:
```bash
python manage.py run_discovery \
    --theme "logistics companies" \
    --geography "US,GB" \
    --entity-types logistics_company freight_forwarder \
    --max-queries 20 \
    --dry-run
```
|----------|--------|-------------|
| /api/content/opportunities/ | GET | Generate opportunities on-the-fly |
| /api/content/opportunities/batch/ | POST/GET | Batch generation |
| /api/content/opportunities/trending-topics/ | GET | Trending topics |
| /api/content/opportunities/coverage-stats/ | GET | Coverage gaps |
| /api/content/opportunities/saved/ | CRUD | Persisted opportunities |
| /api/content/opportunities/saved/{id}/start-draft/ | POST | Generate draft |
| /api/content/draft/ | POST | Generate draft on-the-fly |
| /api/content/drafts/saved/ | CRUD | Persisted drafts |
| /api/content/drafts/saved/{id}/regenerate/ | POST | Regenerate with feedback |
| /api/content/drafts/saved/{id}/refine/ | POST | Refine section |
| /api/content/drafts/saved/{id}/publish/ | POST | Mark published |
| /api/content/templates/ | CRUD | Synthesis templates |

**Celery Tasks** (apps/content/tasks.py):
- generate_opportunities, generate_opportunities_batch, expire_old_opportunities
- generate_draft, regenerate_draft, refine_draft
- opportunity_to_draft_pipeline, cleanup_old_drafts

### Phase 11.1 (API Gap Analysis Fixes)
Security & Error Handling:
- apps/core/security.py - SSRFGuard, URLNormalizer, SafeHTTPClient (SSRF protection)
- apps/core/exceptions.py - ErrorCode enum (35+ codes), EMCIPException, emcip_exception_handler
- config/settings/base.py - Added custom exception handler to REST_FRAMEWORK

Seeds Enhancements:
- apps/seeds/models.py - Added normalized_url (unique), seed_type, confidence, country, regions, topics, discovered_from_source, discovered_from_run
- apps/seeds/migrations/0002_add_seed_classification_fields.py - Migration for new fields
- apps/seeds/serializers.py - Added value (url alias), discovered_from, new fields
- apps/seeds/views.py - Added 15+ filters (q, seed_type, country, region, topic, ordering, date range, confidence)
- apps/seeds/views.py - SeedDiscoverEntrypointsView, SeedTestCrawlView (new endpoints)
- apps/seeds/views.py - Updated SeedValidateView to use SafeHTTPClient
- apps/seeds/urls.py - Added discover-entrypoints, test-crawl routes

Sources Enhancements:
- apps/sources/serializers.py - SourceListSerializer, SourceDetailSerializer, SourceCreateSerializer, SourceUpdateSerializer, SourceTestSerializer
- apps/sources/views.py - SourceViewSet (full CRUD), test_source action, crawl_now action, SourceStatsView
- apps/sources/urls.py - Updated routes for Source CRUD + actions

Runs Enhancements:
- apps/sources/views.py - RunViewSet now supports POST /api/runs/ (create alias), started_after/before filters, ordering

Articles Enhancements:
- apps/articles/views.py - Added filters: language, score_gte/lte, has_images, has_citations, has_statistics, date ranges, ordering
- apps/articles/views.py - Added actions: reprocess, mark-used, mark-ignored
- apps/articles/views.py - ArticleBulkActionView, ArticleExportView (CSV/JSON)
- apps/articles/urls.py - Added bulk, export routes

### Phase 10.7 (HTMX Templates)
- templates/base.html - Main layout with Tailwind CSS, HTMX, Alpine.js
- templates/console/login.html - Login page
- templates/console/dashboard.html - Dashboard with stats, activity, health
- templates/console/sources.html - Sources and runs management
- templates/console/schedules.html - Schedule management
- templates/console/seeds.html - Seed URL management
- templates/console/articles.html - Article listing
- templates/console/article_detail.html - 7-tab article detail view
- templates/console/llm_settings.html - LLM configuration and monitoring
- templates/console/partials/*.html - 18 HTMX partials for dynamic updates
- templates/console/modals/*.html - 4 modal templates
- apps/core/console_views.py - 22 view classes for console
- apps/core/console_urls.py - 22 URL patterns mounted at /console/
- config/urls.py - Added console route

### Phase 10.5 (Article Viewer)
- apps/articles/views.py - ArticleListView, ArticleDetailView, ArticleStatsView, ArticleReprocessView
- apps/articles/serializers.py - Article serializers
- apps/articles/urls.py - Article URL patterns
- apps/articles/tests/test_articles_api.py - 19/19 tests passing

### Phase 10.4 (Seeds Manager)
- apps/seeds/ - New app for seed management
- apps/seeds/models.py - Seed, SeedCategory models
- apps/seeds/views.py - SeedViewSet, SeedCategoryViewSet, SeedImportView
- apps/seeds/tests/test_seeds_api.py - 27/27 tests passing

### Phase 10.3 (Schedule Editor)
- apps/core/models.py - Added CrawlSchedule model
- apps/sources/views.py - ScheduleViewSet API
- apps/sources/serializers.py - ScheduleSerializer with interval/crontab support
- apps/sources/tests/test_schedules_api.py - 20/20 tests passing

### Phase 10.2 (Sources & Runs API)
- apps/sources/views.py - SourceViewSet, SourceConfigView, CrawlJobViewSet, TriggerCrawlView
- apps/sources/serializers.py - Source, CrawlJob serializers
- apps/sources/urls.py - API routes
- apps/sources/tests/test_sources_api.py - 19/19 tests passing

### Phase 10.1 (JWT Auth)
- apps/core/views.py - Login, Logout, Refresh, User views
- apps/core/serializers.py - Auth serializers
- apps/core/urls.py - Auth URL patterns
- apps/core/tests/test_auth.py - 14/14 tests passing

**Last successful tests**:
- Phase 10.1: 14/14 auth tests passed
- Phase 10.2: 19/19 sources API tests passed
- Phase 10.3: 20/20 schedules API tests passed
- Phase 10.4: 27/27 seeds API tests passed
- Phase 10.5: 19/19 articles API tests passed
- Phase 10.6: 31/31 LLM settings tests passed

## Key Decisions Made
- **Database**: PostgreSQL (for relational integrity and JSON support)
- **Translation**: Google Translate API initially (can swap to DeepL later)
- **LLM**: Claude Sonnet 4 primary, GPT-4 fallback
- **Crawlers**: Scrapy for most sources, Playwright for JS-heavy sites
- **Storage**: Local PostgreSQL for dev, S3 for production
- **Task Queue**: Celery + Redis
- **Python Version**: 3.11+
- **Django Version**: 5.0+

## Known Issues
None outstanding

## Environment
- Python: 3.11+ (to be installed)
- Django: 5.0.1 (to be installed)
- PostgreSQL: 15+ (to be installed)
- Redis: 7.0+ (to be installed)
- Running in: Local development (Docker for production)

## API Keys Configured
- [ ] Anthropic (Claude)
- [ ] Google Translate
- [ ] OpenAI (optional fallback)
- [ ] AWS S3 (for production)

## Test Coverage
Not yet implemented

## Recent Sessions Log
**Session 28** (2025-12-24): Final Verification - Confirmed orchestration lifecycle (per-source timestamps, atomic aggregation, cancellation); Sources CRUD/test/crawl-now working; Runs alias/totals/filters verified; ExportJob with cleanup_old_exports task added; Permissions audit (IsAdmin on SchedulePauseAllView, DestructiveActionPermission on ScheduleViewSet); Metrics wired (increment_runs_started, increment_schedules_trigger); Request ID propagation complete; Indexes on all major models verified; Docs aligned with implementation
**Session 27** (2025-12-24): Error Taxonomy & API Consistency - ErrorCode alignment, export status_url/download_url, query indexes
**Session 25** (2025-12-23): Phase 15 Production Deployment - Docker Compose, OpenTelemetry tracing, Nginx, production settings
**Session 24** (2025-12-23): Phase 14 API Improvements - Seeds merge, ExportJob async, orchestration fixes, DRF router fix
**Session 23** (2025-12-23): Phase 14 Observability - Metrics, request ID middleware, throttling, permissions
**Session 22** (2025-12-23): Phase 11.1 API Gap Analysis Fixes - SSRFGuard, URLNormalizer, SafeHTTPClient for security; ErrorCode enum with 35+ codes and custom exception handler; Seeds: 8 new model fields + migration, 15+ filters, discover-entrypoints/test-crawl endpoints; Sources: full CRUD ViewSet with test/crawl-now actions; Runs: POST alias, date range filters; Articles: 10+ new filters, reprocess/mark-used/mark-ignored actions, bulk actions, CSV/JSON export
**Session 21** (2025-12-23): Phase 10.7 HTMX Templates - Complete Operator Console UI with Tailwind CSS, HTMX, Alpine.js; 8 main templates, 18 partials, 4 modals, 22 views, 22 URLs
**Session 20** (2025-12-23): Phase 10.6 LLM Settings - LLMSettings/LLMUsageLog models, 8 API views, usage stats, budget tracking, models list, 31/31 tests passing
**Session 19** (2025-12-23): Phase 9 Final Integration - Fixed integration test API mismatches, added get_default_registry(), updated package exports, all 30/30 integration tests passing, all phases validated
**Session 18** (2025-12-23): Phase 8 Observability - StructuredLogger, MetricsCollector (counters/gauges/histograms/timers), HealthChecker with built-in checks, @timed/@counted/@logged decorators, RequestTracer, health endpoints, 15/15 tests passing
**Session 17** (2025-12-23): Phase 7 LLM Hardening - PromptTemplate/Registry, token counting, cost tracking, response caching, enhanced ClaudeClient, 12/12 tests passing
**Session 16** (2025-12-23): Phase 6 State Machine - ArticleState enum, ArticleStateMachine with hooks/retry, ProcessingPipeline, StateMachineProcessor, 10/10 tests passing
**Session 15** (2025-12-23): Phase 5 Extraction Quality - TrafilaturaExtractor, HybridContentExtractor, EnhancedArticleExtractor, 9/9 tests passing
**Session 14** (2025-12-23): Phase 4 Playwright - PlaywrightFetcher, HybridFetcher, updated factory, 10/10 tests passing
**Session 13** (2025-12-23): Phase 3 Pagination Memory - Source.pagination_state, get_combined_config, 4/4 tests passing
**Session 12** (2025-12-23): Phase 2 Interface Abstractions - Fetcher/LinkExtractor/Paginator ABCs, ModularCrawler
**Session 11** (2025-12-23): Crawler utilities - rate limiting, async fetch, URL normalization
**Session 10** (2025-12-23): Pagination strategies - ParameterPaginator, PathPaginator, NextLinkPaginator
**Session 9** (2025-12-23): Article scoring - heuristic scoring, AI detection penalty, quality badges
**Session 8** (2025-12-23): Claude API integration - lightweight wrapper to classify AI content
**Session 7** (2025-12-23): Translation - Google Translate HTTP/client support with graceful fallback
**Session 6** (2025-12-23): Text extraction - newspaper3k-based extractor and processing script
**Session 5** (2024-12-20): Celery task queue - CrawlJob model, async crawl_source task
**Session 4** (2024-12-20): Basic crawler - BaseCrawler, ScrapyCrawler with article link detection
**Session 3** (2024-12-20): Admin interfaces - SourceAdmin and ArticleAdmin
**Session 2** (2024-12-20): Core models - BaseModel, Source, Article, migrations
**Session 1** (2024-12-20): Django project setup - all apps, settings, and configuration
**Session 0** (2024-12-20): Phase 0 preparation - creating tracking files
