# Operator Console MVP - Project State

## Current Phase
**Phase 10.5**: Article Viewer (COMPLETE) ✅

## Session Info
- **Date**: 2025-12-23 (Current Session)
- **Previous Session**: Phase 9 Complete - All Core Phases Done
- **Initiative**: Operator Console MVP (Phases 10.0 - 10.6)

## Phase Progress
| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| 10.0 | Recon + Baseline | ✅ Complete | 30/30 |
| 10.1 | JWT Auth | ✅ Complete | 10/10 |
| 10.2 | Runs API | ✅ Complete | 15/15 |
| 10.3 | Schedules API | ✅ Complete | 15/15 |
| 10.4 | Seeds App | ✅ Complete | 18/18 |
| 10.5 | Article Viewer | ✅ Complete | 19/19 |
| 10.6 | LLM Settings | ⏳ Not Started | - |

**Total Tests**: 107 passing

## Environment
- **Django**: 5.0.1
- **DRF**: 3.14.0
- **SimpleJWT**: 5.3.1
- **django-celery-beat**: 2.7.0
- **Celery**: 5.6.0
- **Redis**: 7.1.0
- **Python**: 3.13.5
- **Database**: PostgreSQL (SQLite fallback for dev)

## Key Decisions (from Clarifying Questions)

### 1. Phase Numbering
Phase 10+ (continuing from Phase 9). Internal sub-phases: 10.0 - 10.6

### 2. Auth Strategy
SimpleJWT (djangorestframework-simplejwt)
- TokenObtainPairView at `/api/auth/login/`
- TokenRefreshView at `/api/auth/refresh/`

### 3. User Model
- Django default `User` model
- New `OperatorProfile` with 1-1 relationship to User
- Fields: preferences (JSON), role, settings

### 4. Seed Storage
- New `apps/seeds` app
- `Seed` model (url, status, discovered_at, promoted_to_source_id, etc.)
- Import/promote wizard with validation

### 5. Run = Extended CrawlJob
- Extend existing `CrawlJob` model (don't replace)
- Add: `config_overrides` (JSON), `priority`, `triggered_by`
- New `CrawlJobSourceResult` model for multi-source runs

### 6. Article Related Models (not JSONFields)
- `ArticleRawCapture` (raw_html, headers, http_status)
- `ArticleScoring` (each score component breakdown)
- `ArticleLLMArtifact` (LLM prompt/response pairs)
- `ArticleImage` (url, alt_text, analysis)

### 7. Scheduling
- `django-celery-beat` (DB-backed)
- `PeriodicTask` for schedules
- Replace file-based CELERY_BEAT_SCHEDULE

### 8. Templates
- App-level: `apps/<app>/templates/<app>/`
- Base template in `templates/base.html`
- HTMX + AlpineJS patterns

### 9. LLM Settings
- Use existing `ClaudeClient`, `CostTracker`, `PromptRegistry`
- Add thin `LLMSettings` model for persistence
- Fields: default_model, temperature, daily_budget, enabled_features

### 10. Version Control
- Commit after each task/phase
- Meaningful commit messages

### 11. Testing
- pytest-django with best coverage approach
- Test each API endpoint
- Test model validations
- Test task execution

## Existing Infrastructure Summary

### Models
| Model | Location | Key Fields |
|-------|----------|------------|
| BaseModel | apps/core/models.py | id (UUID), created_at, updated_at |
| Source | apps/sources/models.py | name, domain, url, reputation_score, status, crawler_config, pagination_state |
| CrawlJob | apps/sources/models.py | source FK, status, started_at, completed_at, total_found, new_articles, errors, task_id |
| Article | apps/articles/models.py | source FK, url, title, processing_status, total_score, extracted_text, translated_text |

### Existing API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/content/opportunities/ | GET | Find content opportunities |
| /api/content/draft/ | POST | Generate draft from articles |
| /api/content/articles/top/ | GET | Get top-scored articles |
| /health/ | GET | Health check |
| /livez/ | GET | Liveness probe |
| /readyz/ | GET | Readiness probe |
| /metrics/ | GET | Prometheus metrics |
| /status/ | GET | System status |

### Celery Tasks
| Task | Queue | Purpose |
|------|-------|---------|
| crawl_source | crawl | Crawl single source |
| crawl_all_active_sources | crawl | Queue all active sources |
| extract_article_text | process | Extract article content |
| translate_article | process | Translate article |
| score_article | process | Score article |
| process_article_pipeline | process | Full article pipeline |

### LLM Components (Phase 7)
- `ClaudeClient` - Claude API wrapper with caching
- `PromptRegistry` - Versioned prompt templates
- `CostTracker` - Usage and cost tracking
- `ResponseCache` - LLM response caching

### Observability (Phase 8)
- `StructuredLogger` - JSON structured logging
- `MetricsCollector` - Prometheus-style metrics
- `HealthChecker` - Component health checks

## Blocked / Risks
- None identified yet

## Next Actions
1. Create remaining state files (TODO.md, ENDPOINTS.md, SCHEMA.md, TESTING.md, CHANGELOG.md, SESSION_LOG.md)
2. Complete Phase 0 baseline documentation
3. Begin Phase 1: JWT Auth Foundation
