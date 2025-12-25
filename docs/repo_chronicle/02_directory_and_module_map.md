# 02 Directory and Module Map

> **Purpose**: Comprehensive mapping of every file and folder with explanations of purpose, key exports, and interdependencies.

---

## 1. Root Directory Structure

```
EMCIP/
├── apps/                    # Django applications (business logic)
├── config/                  # Django project configuration
├── docs/                    # Documentation
├── logs/                    # Log file output directory
├── scripts/                 # Utility and testing scripts
├── static/                  # Static files (CSS, JS, images)
├── templates/               # Django HTML templates
├── db.sqlite3               # SQLite database (development)
├── manage.py                # Django management CLI
├── requirements.txt         # Python dependencies (full)
├── requirements-dev.txt     # Development dependencies
├── requirements-minimal.txt # Minimal production dependencies
├── BUILD_LOG.md             # Development session log
├── PROJECT_STATE.md         # Current project status
└── README.md                # Project overview and setup
```

---

## 2. Configuration Module (`config/`)

```
config/
├── __init__.py              # Package marker (loads celery app)
├── asgi.py                  # ASGI application entry point
├── wsgi.py                  # WSGI application entry point
├── celery.py                # Celery application configuration
├── routers.py               # Custom DRF router (SafeDefaultRouter)
├── urls.py                  # Root URL configuration
└── settings/
    ├── __init__.py          # Settings package (imports from env-specific)
    ├── base.py              # Shared settings for all environments
    ├── development.py       # Development-specific overrides
    └── production.py        # Production-specific settings
```

### 2.1 Key Files Explained

| File | Purpose | Key Exports |
|------|---------|-------------|
| `celery.py` | Celery app initialization, task autodiscovery, routing | `app` (Celery application) |
| `urls.py` | Maps URL patterns to views across all apps | `urlpatterns` list |
| `routers.py` | SafeDefaultRouter that filters registered viewsets | `SafeDefaultRouter` class |
| `settings/base.py` | All Django/DRF/Celery/LLM configuration | Django settings dict |

### 2.2 Settings Structure

```python
# settings/base.py - Key sections
INSTALLED_APPS = [
    # Django built-ins
    # Third-party apps (rest_framework, celery, etc.)
    # EMCIP apps
]

REST_FRAMEWORK = {
    # Authentication, permissions, throttling, pagination
}

CELERY_* = {
    # Broker URL, task routes, serialization, beat scheduler
}

LLM_* = {
    # Model, max tokens, temperature
}
```

---

## 3. Core Application (`apps/core/`)

```
apps/core/
├── __init__.py              # Package marker
├── apps.py                  # Django app configuration
├── models.py                # BaseModel, OperatorProfile
├── exceptions.py            # Custom exception classes and handler
├── middleware.py            # RequestIDMiddleware
├── security.py              # HTTPFetcher (SSRF protection)
├── metrics.py               # Prometheus metrics definitions
└── migrations/
    ├── __init__.py
    └── 0001_initial.py      # OperatorProfile migration
```

### 3.1 Key Exports

| File | Key Classes/Functions |
|------|----------------------|
| `models.py` | `BaseModel` (UUID pk, timestamps), `OperatorProfile` (user roles) |
| `exceptions.py` | `custom_exception_handler()`, `EMCIPException` |
| `middleware.py` | `RequestIDMiddleware` |
| `security.py` | `HTTPFetcher.fetch()`, `validate_url()` |
| `metrics.py` | `articles_processed_total`, `crawl_duration_seconds` |

### 3.2 BaseModel Pattern

All models inherit from `BaseModel`:

```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

---

## 4. Sources Application (`apps/sources/`)

```
apps/sources/
├── __init__.py              # Package marker
├── admin.py                 # Django admin registration
├── apps.py                  # Django app configuration
├── models.py                # Source, CrawlJob, CrawlJobSourceResult
├── serializers.py           # DRF serializers for API
├── views.py                 # API ViewSets
├── urls.py                  # URL patterns
├── tasks.py                 # Celery tasks (crawl_source)
├── crawlers/
│   ├── __init__.py          # Crawler factory function
│   ├── base.py              # BaseCrawler abstract class
│   ├── registry.py          # Crawler type registry
│   ├── scrapy_crawler.py    # Scrapy-based crawler
│   └── extractors.py        # HybridContentExtractor
└── migrations/
    ├── 0001_initial.py      # Source model
    ├── 0002_crawljob.py     # CrawlJob model
    └── ...                  # Additional migrations
```

### 4.1 Key Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Source` | News source configuration | `name`, `domain`, `crawler_type`, `crawler_config`, `priority` |
| `CrawlJob` | Individual crawl execution | `source`, `status`, `task_id`, `total_found`, `new_articles` |
| `CrawlJobSourceResult` | Per-source result in multi-source crawl | `crawl_job`, `source`, `articles_found` |

### 4.2 Crawler Architecture

```
BaseCrawler (abstract)
    │
    ├── RequestsCrawler      # Simple HTTP requests
    ├── ScrapyCrawler        # Scrapy framework integration
    └── PlaywrightCrawler    # Browser automation (reserved)
```

---

## 5. Seeds Application (`apps/seeds/`)

```
apps/seeds/
├── __init__.py              # Package marker
├── admin.py                 # Django admin registration
├── apps.py                  # Django app configuration
├── models.py                # Seed, SeedRawCapture, DiscoveryRun models
├── serializers.py           # DRF serializers
├── views.py                 # API ViewSets
├── urls.py                  # URL patterns
├── tasks.py                 # Celery tasks (validate_seed, discover_seeds)
├── validators.py            # URL validation logic
├── discovery/               # Phase 16: Discovery Pipeline
│   ├── __init__.py          # Package exports
│   ├── connectors.py        # SERP, RSS, HTML directory connectors
│   ├── query_generator.py   # LLM-powered query expansion
│   ├── classifier.py        # Page/entity type classification
│   ├── scoring.py           # Multi-factor seed scoring
│   └── tasks.py             # Discovery Celery tasks with sync fallback
├── management/
│   └── commands/
│       └── run_discovery.py # CLI discovery command
└── migrations/
    ├── 0001_initial.py      # Seed model
    ├── 0002_seedbatch.py    # SeedBatch model
    ├── 0003_add_query_indexes.py
    └── 0004_discovery_architecture.py  # Phase 16 models
```

### 5.1 Seed Model

```python
class Seed(BaseModel):
    url = models.URLField(max_length=2048)
    normalized_url = models.CharField(max_length=2048)  # Dedup key
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    status = models.CharField(choices=STATUS_CHOICES)
    seed_type = models.CharField(choices=TYPE_CHOICES)
    discovered_at = models.DateTimeField()
    validated_at = models.DateTimeField(null=True)
    promoted_at = models.DateTimeField(null=True)
    promoted_article = models.ForeignKey(Article, null=True)
    
    # Phase 16: Discovery provenance
    query_used = models.CharField(max_length=500, blank=True)
    referrer_url = models.URLField(max_length=2000, blank=True)
    discovery_run_id = models.UUIDField(null=True, db_index=True)
    
    # Phase 16: Multi-dimensional scoring
    relevance_score = models.IntegerField(default=0)
    utility_score = models.IntegerField(default=0)
    freshness_score = models.IntegerField(default=0)
    authority_score = models.IntegerField(default=0)
    overall_score = models.IntegerField(default=0, db_index=True)
    
    # Phase 16: Scrape planning
    scrape_plan_hint = models.CharField(max_length=50, blank=True)
    recommended_entrypoints = models.JSONField(default=list)
    expected_fields = models.JSONField(default=list)
    
    # Phase 16: Review workflow
    review_status = models.CharField(max_length=20, default='pending')
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True)
    reviewed_by = models.ForeignKey(User, null=True)
```

### 5.2 Seed Workflow

```
[Discover] → [pending] → [Validate] → [valid] → [Review] → [Promote] → [promoted]
                                   └─→ [invalid]         └─→ [rejected]
```

### 5.3 Discovery Pipeline (Phase 16)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  TargetBrief    │───▶│ QueryGenerator  │───▶│   Connectors    │
│ (theme, geo)    │    │ (LLM + fallback)│    │ (SERP/RSS/HTML) │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Seed        │◀───│   SeedScorer    │◀───│ SeedClassifier  │
│   (created)     │    │ (multi-factor)  │    │ (page/entity)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       ▲
                                                       │
                                              ┌────────┴────────┐
                                              │ SeedRawCapture  │
                                              │ (gzip + hash)   │
                                              └─────────────────┘
```

| Module | Purpose |
|--------|---------|
| `connectors.py` | BaseConnector, SERPConnector, RSSConnector, HTMLDirectoryConnector |
| `query_generator.py` | LLM query expansion with template fallback |
| `classifier.py` | Lightweight page type and entity detection |
| `scoring.py` | Weighted multi-factor scoring (relevance, utility, freshness, authority) |
| `tasks.py` | Celery tasks with sync fallback for CLI |

---

## 6. Articles Application (`apps/articles/`)

```
apps/articles/
├── __init__.py              # Package marker
├── admin.py                 # Django admin registration
├── apps.py                  # Django app configuration
├── models.py                # Article, ExportJob, related models
├── serializers.py           # DRF serializers
├── views.py                 # API ViewSets
├── urls.py                  # URL patterns
├── tasks.py                 # Celery tasks (extract, translate, score)
├── services.py              # ArticleExtractor, Translator, Scorer, Processor
└── migrations/
    ├── 0001_initial.py      # Article model
    └── ...                  # Additional migrations
```

### 6.1 Key Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Article` | Core content entity | `url`, `title`, `extracted_text`, `processing_status`, `total_score` |
| `ArticleRawCapture` | Original HTML storage | `article`, `raw_html`, `capture_method` |
| `ArticleScoreBreakdown` | Detailed scoring | `article`, `relevance_score`, `timeliness_score` |
| `ArticleLLMArtifact` | LLM-generated content | `article`, `artifact_type`, `content` |
| `ArticleImage` | Extracted images | `article`, `url`, `caption` |
| `ExportJob` | Async export tracking | `format`, `status`, `file_path`, `params` |

### 6.2 Service Classes

| Class | Purpose | Key Methods |
|-------|---------|-------------|
| `ArticleExtractor` | HTML to text | `extract(article)` |
| `ArticleTranslator` | Non-English to English | `translate_article(article)` |
| `ArticleScorer` | Quality scoring | `score_article(article)` |
| `ArticleProcessor` | Full pipeline | `process(article_id, translate, score)` |

---

## 7. Content Application (`apps/content/`)

```
apps/content/
├── __init__.py              # Package marker
├── apps.py                  # Django app configuration
├── models.py                # ContentOpportunity, ContentDraft, templates
├── serializers.py           # DRF serializers (extensive)
├── views.py                 # API ViewSets (743 lines)
├── urls.py                  # URL patterns
├── tasks.py                 # Celery tasks (generate_opportunities, generate_draft)
├── opportunity.py           # OpportunityFinder class
├── synthesis.py             # DraftGenerator class
├── llm.py                   # ClaudeClient wrapper
├── prompts.py               # Prompt template registry
└── token_utils.py           # Token counting, caching, cost tracking
```

### 7.1 Key Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `ContentOpportunity` | Detected content opportunity | `headline`, `angle`, `opportunity_type`, `composite_score` |
| `OpportunityBatch` | Batch opportunity generation job | `config`, `status`, `opportunities_found` |
| `ContentDraft` | Generated content | `title`, `content`, `content_type`, `quality_score` |
| `DraftFeedback` | User feedback on drafts | `draft`, `rating`, `feedback_text` |
| `SynthesisTemplate` | Custom generation templates | `name`, `prompt_template`, `content_type` |

### 7.2 LLM Integration

```python
# apps/content/llm.py
class ClaudeClient:
    def __init__(self, api_key, model, max_tokens, temperature):
        pass
    
    @property
    def available(self) -> bool:
        """Returns True if API key configured."""
        pass
    
    def _run_prompt(self, prompt, system, max_tokens) -> str:
        """Execute prompt against Claude API."""
        pass

def parse_llm_json(raw_text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    pass
```

---

## 8. Workflows Application (`apps/workflows/`)

```
apps/workflows/
├── __init__.py              # Package marker
├── apps.py                  # Django app configuration
└── (reserved for future)    # Orchestration logic
```

**Status**: Reserved for future implementation. Will handle:
- Complex multi-step workflows
- Pipeline orchestration
- Conditional execution paths

---

## 9. Analytics Application (`apps/analytics/`)

```
apps/analytics/
├── __init__.py              # Package marker
├── apps.py                  # Django app configuration
└── (reserved for future)    # Metrics and reporting
```

**Status**: Reserved for future implementation. Will handle:
- Dashboard metrics
- Trend analysis
- System health reporting

---

## 10. Templates Directory (`templates/`)

```
templates/
├── base.html                # Base layout template
└── console/                 # HTMX-based Operator Console
    ├── dashboard.html       # Main dashboard
    ├── sources.html         # Sources management
    ├── seeds.html           # Seeds list
    ├── seeds_review.html    # Phase 16: Seed review queue
    ├── articles.html        # Articles list
    ├── article_detail.html  # Article details
    ├── schedules.html       # Schedule management
    ├── llm_settings.html    # LLM configuration
    ├── login.html           # Authentication
    ├── partials/            # HTMX partial templates
    │   ├── dashboard_stats.html
    │   ├── seeds_list.html
    │   ├── seeds_review_queue.html  # Phase 16: Review queue
    │   ├── discovery_runs.html      # Phase 16: Discovery runs list
    │   ├── seed_row.html            # Phase 16: Single seed row
    │   └── ...
    └── modals/              # HTMX modal templates
        ├── discovery_new.html       # Phase 16: New discovery form
        └── capture_preview.html     # Phase 16: Raw capture preview
```

---

## 12. Scripts Directory (`scripts/`)

```
scripts/
├── create_superuser.py      # Programmatic superuser creation
├── test_article_processing.py  # Manual article processing test
├── test_celery_task.py      # Celery task testing
├── test_crawler.py          # Crawler testing
└── test_models.py           # Model testing
```

---

## 13. Documentation (`docs/`)

```
docs/
├── TESTING_GUIDE.md         # Testing procedures
├── agent/
│   ├── CHANGELOG.md         # Change log per session
│   ├── SESSION_LOG.md       # Detailed session notes
│   └── TODO.md              # Remaining work items
└── repo_chronicle/          # This documentation set
    ├── 000_llm_agent_instruction.md
    ├── 00_repo_overview.md
    ├── 01_system_architecture.md
    ├── 02_directory_and_module_map.md  # (this file)
    └── ...
```

---

## 12. Module Dependencies

### 12.1 Import Graph

```
config.settings.base
    ↓
apps.core.models
    ↓
apps.sources.models ──────────────────────┐
    ↓                                     │
apps.seeds.models ←───────────────────────┤
    ↓                                     │
apps.articles.models ←────────────────────┘
    ↓
apps.content.models
    ↓
apps.content.llm
```

### 12.2 Circular Import Prevention

The codebase uses lazy imports to prevent circular dependencies:

```python
# apps/content/tasks.py
def _get_models():
    """Lazy import to avoid circular imports."""
    from apps.content.models import ContentOpportunity, OpportunityBatch, ContentDraft
    return ContentOpportunity, OpportunityBatch, ContentDraft
```

---

## 13. File Naming Conventions

| Pattern | Purpose | Example |
|---------|---------|---------|
| `models.py` | Django model definitions | `apps/articles/models.py` |
| `views.py` | DRF ViewSets and APIViews | `apps/sources/views.py` |
| `serializers.py` | DRF serializers | `apps/content/serializers.py` |
| `tasks.py` | Celery task definitions | `apps/sources/tasks.py` |
| `services.py` | Business logic classes | `apps/articles/services.py` |
| `urls.py` | URL route definitions | `apps/seeds/urls.py` |
| `admin.py` | Django admin configuration | `apps/sources/admin.py` |
| `apps.py` | Django app configuration | `apps/core/apps.py` |

---

## 14. Key File Line Counts

| File | Lines | Complexity |
|------|-------|------------|
| `config/settings/base.py` | ~330 | High - all configuration |
| `apps/articles/models.py` | ~880 | High - core data model |
| `apps/articles/services.py` | ~875 | High - processing logic |
| `apps/content/views.py` | ~743 | High - full API surface |
| `apps/content/synthesis.py` | ~696 | Medium - LLM generation |
| `apps/sources/models.py` | ~615 | Medium - source/crawl models |
| `apps/content/models.py` | ~643 | Medium - opportunity/draft models |

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
