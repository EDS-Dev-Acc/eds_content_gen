# EMCIP Stack Upgrade Plan

## Executive Summary

This document outlines the upgrade plan for the EMCIP Django/Celery crawler pipeline. The upgrade introduces production-grade infrastructure, improved crawling capabilities, and enhanced LLM integration while maintaining backwards compatibility.

---

## Current Baseline Architecture

### Core Stack
| Component | Version | Notes |
|-----------|---------|-------|
| Django | 5.0.1 | DRF 3.14.0 |
| Database | SQLite | Postgres-ready via settings |
| Task Queue | Celery 5.6.0 | Redis broker/backend configured |
| Python | 3.11+ | Type hints used throughout |

### Application Structure

```
apps/
├── sources/           # Source management + crawling
│   ├── models.py      # Source, CrawlJob models
│   ├── tasks.py       # crawl_source, crawl_all_active_sources
│   ├── crawlers/
│   │   ├── base.py           # BaseCrawler ABC
│   │   ├── scrapy_crawler.py # HTTP crawler (requests + bs4)
│   │   ├── registry.py       # Site-specific tuning rules
│   │   └── utils.py          # URLNormalizer, RateLimiter, async fetch
│   └── admin.py
├── articles/          # Article storage + processing
│   ├── models.py      # Article model (47 fields)
│   ├── services.py    # Extractor, Translator, Scorer, Processor
│   ├── tasks.py       # extract/translate/score tasks
│   └── admin.py
├── content/           # LLM-powered content generation
│   ├── llm.py         # ClaudeClient wrapper
│   ├── opportunity.py # OpportunityFinder
│   ├── synthesis.py   # DraftGenerator
│   ├── views.py       # API endpoints
│   └── urls.py
├── core/              # Shared base models
├── workflows/         # (Placeholder)
└── analytics/         # (Placeholder)
```

### Current Pipeline Flow

```
[Source] → [Crawler] → [Article(collected)]
                              ↓
                     [Extractor] → [Article(extracted)]
                              ↓
                     [Translator] → [Article(translated)]
                              ↓
                     [Scorer] → [Article(scored/completed)]
                              ↓
              [OpportunityFinder] → [DraftGenerator]
```

### Key Capabilities Already Implemented

| Feature | Status | Location |
|---------|--------|----------|
| HTTP crawling | ✅ | `scrapy_crawler.py` |
| Pagination (3 types) | ✅ | `scrapy_crawler.py` |
| URL normalization | ✅ | `utils.py` |
| Per-domain rate limiting | ✅ | `utils.py` |
| Async parallel fetch | ✅ | `utils.py` (aiohttp) |
| Text extraction | ✅ | `newspaper3k` |
| Language detection | ✅ | `langdetect` |
| Translation | ✅ | Google Translate API |
| Multi-factor scoring | ✅ | `services.py` |
| AI content detection | ✅ | Claude + heuristic fallback |
| Opportunity generation | ✅ | `opportunity.py` |
| Draft synthesis | ✅ | `synthesis.py` |
| Celery task queue | ✅ | Task-per-stage pattern |

---

## Upgrade Phases Overview

### Phase 1: Environment & Data Backbone
- Docker Compose for local dev (Postgres + Redis)
- Postgres as production database
- Redis as Celery broker/backend

### Phase 2: Pipeline Refactor (Interfaces)
- Introduce Fetcher, LinkExtractor, Paginator interfaces
- Wrap existing logic into adapters
- Enable pluggable backends

### Phase 3: Pagination + "What Worked" Memory
- Already partially done - enhance with success persistence
- Template pagination via registry
- Next-link pagination fallback
- Store last-success mode per source

### Phase 4: JS Handling (Playwright)
- Add PlaywrightFetcher for JS-rendered pages
- Source-level fetcher selection
- Hybrid mode (HTTP first, fallback to browser)

### Phase 5: Extraction Quality
- Add trafilatura as primary extractor
- newspaper3k as fallback
- Image extraction as first-class enrichment

### Phase 6: State Machine / Enums
- Formalize processing states with Enums
- Add stage timestamps
- Enable selective reprocessing

### Phase 7: LLM Service Hardening
- Centralized LLM service boundary
- Schema validation (Pydantic)
- Response caching
- Prompt versioning

### Phase 8: Frontend + API Safety
- JWT/session auth
- Rate limiting
- Minimal UI (HTMX or Next.js)

### Phase 9: Observability
- Structured JSON logging
- Correlation IDs
- Metrics (Prometheus/Sentry)

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Data loss during Postgres migration | Keep SQLite backup, test migrations |
| Breaking existing crawlers | Adapter pattern, gradual migration |
| LLM API changes | Version prompts, cache responses |
| Performance regression | Benchmark before/after each phase |

---

## Dependencies to Add

| Package | Purpose | Phase |
|---------|---------|-------|
| `psycopg2-binary` | Postgres driver | 1 |
| `trafilatura` | Better extraction | 5 |
| `readability-lxml` | Fallback extraction | 5 |
| `playwright` | JS rendering | 4 |
| `pydantic` | Schema validation | 7 |
| `sentry-sdk` | Error tracking | 9 |
| `django-htmx` | Frontend (if HTMX) | 8 |

---

## Success Criteria

1. **Baseline preserved**: Existing test scripts pass unchanged
2. **Performance**: Crawl → Score pipeline completes in < 60s per article
3. **Reliability**: Error rate < 5% across 100 articles
4. **Observability**: All pipeline stages traceable via correlation ID
5. **Maintainability**: Code coverage > 70%

---

## Next Steps

1. ~~Run baseline tests to confirm current state~~ ✅
2. ~~Begin Phase 1: Docker Compose setup~~ ✅
3. ~~Migrate to Postgres~~ ✅ (Docker ready, SQLite fallback)
4. ~~Configure Redis as Celery broker~~ ✅
5. ~~Phase 2: Introduce crawler interfaces~~ ✅
6. ~~Begin Phase 3: Pagination persistence + registry enhancements~~ ✅
7. Begin Phase 4: JS Handling (Playwright)

---

## Progress Log

### Phase 0 - Repo Recon (Complete)
- Mapped repository structure
- Created UPGRADE_PLAN.md
- Created BASELINE_TESTS.md
- All baseline tests passing

### Phase 1 - Environment Setup (Complete)
- Created docker-compose.yml (Postgres 15 + Redis 7)
- Updated .env.example with database config
- Created LOCAL_DEV.md documentation
- Enhanced Celery config with beat scheduler and task routing

### Phase 2 - Pipeline Refactor (Complete)
- Created abstract interfaces: `Fetcher`, `LinkExtractor`, `Paginator`
- Implemented `HTTPFetcher` using requests
- Implemented `BS4LinkExtractor` using BeautifulSoup
- Implemented 5 paginator strategies: Parameter, Path, NextLink, Offset, Adaptive
- Created `ModularCrawler` adapter using new interfaces
- Created `CrawlerPipeline` orchestrator
- All baseline tests passing
- New interface tests passing (5/5)

**New Files Created:**
- `apps/sources/crawlers/interfaces.py`
- `apps/sources/crawlers/fetchers/__init__.py`
- `apps/sources/crawlers/fetchers/http_fetcher.py`
- `apps/sources/crawlers/extractors/__init__.py`
- `apps/sources/crawlers/extractors/bs4_link_extractor.py`
- `apps/sources/crawlers/pagination/__init__.py`
- `apps/sources/crawlers/pagination/strategies.py`
- `apps/sources/crawlers/adapters/__init__.py`
- `apps/sources/crawlers/adapters/modular_crawler.py`
- `scripts/test_interfaces.py`

### Phase 3 - Pagination Memory (Complete)
- Added `pagination_state` JSONField to Source model
- Created migration `0004_add_pagination_state`
- Added helper methods to Source:
  - `get_pagination_strategy()` - Get last successful strategy
  - `record_pagination_success()` - Persist successful crawl config
  - `get_preferred_paginator_config()` - Get config for paginator creation
- Updated ModularCrawler to:
  - Use previously successful pagination strategy first
  - Save pagination success after multi-page crawls
- Enhanced registry with:
  - `get_fetcher_config()` - Fetcher settings per domain
  - `get_combined_config()` - Merged config from registry + source + learned
  - `register_site()` / `unregister_site()` - Dynamic registration
- All pagination memory tests passing (4/4)

**Config Priority (highest to lowest):**
1. Source.pagination_state (learned from past success)
2. Registry TUNED_CRAWLERS
3. Source.crawler_config
4. Defaults

**New Files Created:**
- `apps/sources/migrations/0004_add_pagination_state.py`
- `scripts/test_pagination_memory.py`

---

*Generated: 2025-12-23*
*Last Updated: Phase 3 - Pagination Memory Complete*
