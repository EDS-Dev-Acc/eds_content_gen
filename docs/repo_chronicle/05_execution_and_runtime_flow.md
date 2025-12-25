# 05 Execution and Runtime Flow

> **Purpose**: Document exactly what happens when the system starts, processes requests, and executes background tasks.

---

## 1. Application Startup Sequence

### 1.1 Django Startup

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Application Startup                          │
└─────────────────────────────────────────────────────────────────────┘

1. Python Interpreter Initialization
   └─► Load manage.py or wsgi.py/asgi.py

2. Django Settings Load
   └─► config/settings/__init__.py
       └─► Imports base.py
       └─► Detects DJANGO_SETTINGS_MODULE
       └─► Loads environment-specific settings

3. Django Setup (django.setup())
   └─► Initialize logging
   └─► Load INSTALLED_APPS
       ├─► django.contrib.* (admin, auth, etc.)
       ├─► rest_framework
       ├─► django_celery_beat
       ├─► apps.core
       ├─► apps.sources
       ├─► apps.seeds
       ├─► apps.articles
       ├─► apps.content
       ├─► apps.workflows
       └─► apps.analytics

4. URL Resolution Setup
   └─► Load config/urls.py
       └─► Include app URL patterns

5. Middleware Chain Construction
   └─► SecurityMiddleware
   └─► SessionMiddleware
   └─► CommonMiddleware
   └─► CsrfViewMiddleware
   └─► AuthenticationMiddleware
   └─► RequestIDMiddleware  ← Custom
   └─► MessageMiddleware

6. Database Connection Pool
   └─► Establish PostgreSQL/SQLite connection
   └─► Validate migrations

7. Static Files Collection (if WSGI)
   └─► Collect static files

8. Ready for Requests
```

### 1.2 Celery Worker Startup

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Celery Worker Startup                           │
└─────────────────────────────────────────────────────────────────────┘

1. Load Celery App
   └─► config/celery.py
       └─► Create Celery application instance
       └─► Configure from Django settings

2. Django Setup
   └─► django.setup() for ORM access

3. Task Discovery
   └─► Autodiscover tasks from all INSTALLED_APPS
       ├─► apps.sources.tasks (crawl_source, etc.)
       ├─► apps.seeds.tasks (validate_seed, etc.)
       ├─► apps.articles.tasks (extract, translate, score)
       └─► apps.content.tasks (opportunities, drafts)

4. Signal Handlers
   └─► worker_process_init.connect(init_opentelemetry)
       └─► Initialize OpenTelemetry tracing

5. Queue Connection
   └─► Connect to Redis broker
   └─► Subscribe to assigned queues

6. Prefetch Tasks
   └─► Begin accepting tasks from queues

7. Ready for Task Execution
```

### 1.3 Celery Beat Startup

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Celery Beat Startup                            │
└─────────────────────────────────────────────────────────────────────┘

1. Load Celery App
   └─► config/celery.py

2. Initialize Scheduler
   └─► DatabaseScheduler (django_celery_beat)
       └─► Read schedules from database tables

3. Load Periodic Tasks
   └─► Query PeriodicTask model
   └─► Parse crontab/interval schedules

4. Start Scheduler Loop
   └─► Check for due tasks every tick
   └─► Submit tasks to appropriate queues

5. Dynamic Schedule Updates
   └─► Monitor database for schedule changes
   └─► Hot-reload new/modified schedules
```

---

## 2. Request Lifecycle

### 2.1 HTTP Request Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HTTP Request Lifecycle                         │
└─────────────────────────────────────────────────────────────────────┘

Client Request: GET /api/articles/
         │
         ▼
┌─────────────────┐
│  Load Balancer  │ ← SSL termination, health checks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Gunicorn     │ ← WSGI server, worker pool
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Django WSGI    │ ← wsgi.py application entry
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Middleware Stack                              │
├─────────────────────────────────────────────────────────────────────┤
│ SecurityMiddleware        │ HTTPS redirect, security headers       │
│ SessionMiddleware         │ Session loading                        │
│ CommonMiddleware          │ URL normalization                      │
│ CsrfViewMiddleware        │ CSRF protection                        │
│ AuthenticationMiddleware  │ User loading                           │
│ RequestIDMiddleware       │ Generate/attach X-Request-ID           │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  URL Resolver   │ ← Match URL pattern to view
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          DRF Layer                                  │
├─────────────────────────────────────────────────────────────────────┤
│ APIView.dispatch()                                                  │
│   └─► Authentication (JWT token validation)                        │
│   └─► Permission checks                                             │
│   └─► Throttle checks                                               │
│   └─► Content negotiation                                           │
│   └─► Parse request data                                            │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   ViewSet      │ ← Business logic execution
│   .list()      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Serializer   │ ← Data serialization
│   .data        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Response     │ ← HTTP response construction
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Middleware (Response Phase)                      │
├─────────────────────────────────────────────────────────────────────┤
│ RequestIDMiddleware       │ Add X-Request-ID header                │
│ CommonMiddleware          │ Content-Length, etc.                   │
│ SecurityMiddleware        │ Security headers                        │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│    Response    │ ← JSON response to client
│    200 OK      │
└─────────────────┘
```

### 2.2 Authentication Flow (JWT)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     JWT Authentication Flow                         │
└─────────────────────────────────────────────────────────────────────┘

1. Token Acquisition
   Client: POST /api/auth/token/
           {"username": "user", "password": "pass"}
              │
              ▼
   Server: Validate credentials
           Generate access token (5 min expiry)
           Generate refresh token (24h expiry)
              │
              ▼
   Response: {"access": "eyJ...", "refresh": "eyJ..."}

2. Authenticated Request
   Client: GET /api/articles/
           Authorization: Bearer eyJ...
              │
              ▼
   Server: JWTAuthentication.authenticate()
           └─► Decode token
           └─► Validate signature
           └─► Check expiry
           └─► Load User from token claims
              │
              ▼
   ViewSet: request.user = <User instance>

3. Token Refresh
   Client: POST /api/auth/token/refresh/
           {"refresh": "eyJ..."}
              │
              ▼
   Server: Validate refresh token
           Generate new access token
              │
              ▼
   Response: {"access": "eyJ..."}
```

### 2.3 Rate Limiting Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Rate Limiting Flow                             │
└─────────────────────────────────────────────────────────────────────┘

Request arrives at view with throttle_classes
         │
         ▼
┌─────────────────┐
│ Check throttle  │
│ for user/anon   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Allowed    Blocked
    │         │
    │         ▼
    │    ┌─────────────┐
    │    │ 429 Response│
    │    │ Retry-After │
    │    └─────────────┘
    │
    ▼
┌─────────────────┐
│ Process request │
│ Update counter  │
└─────────────────┘

Throttle Classes Applied:
- AnonRateThrottle: 100/day for anonymous
- UserRateThrottle: 1000/day for authenticated
- BurstRateThrottle: 30/min for high-volume endpoints
```

---

## 3. Celery Task Execution

### 3.1 Task Dispatch Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Task Dispatch Flow                             │
└─────────────────────────────────────────────────────────────────────┘

API Request: POST /api/sources/{id}/crawl-now/
         │
         ▼
┌─────────────────┐
│ Create CrawlJob │ ← status='pending'
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ crawl_source    │
│ .delay(args)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Serialize Task  │ ← JSON message
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Redis LPUSH     │ ← Add to 'crawl' queue
│ 'crawl' queue   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Return task_id  │ ← AsyncResult reference
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ API Response    │ ← {"crawl_job_id": "...", "task_id": "..."}
│ 202 Accepted    │
└─────────────────┘
```

### 3.2 Task Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Task Execution Flow                             │
└─────────────────────────────────────────────────────────────────────┘

Celery Worker (crawl queue)
         │
         ▼
┌─────────────────┐
│ Redis BRPOP     │ ← Blocking pop from queue
│ 'crawl' queue   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deserialize     │
│ Task message    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load task func  │ ← crawl_source from registry
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Task Execution                                  │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Get Source from database                                         │
│ 2. Check for cancellation (if parent_job_id)                        │
│ 3. Update CrawlJob status → 'running'                               │
│ 4. Get crawler instance                                              │
│ 5. Execute crawler.crawl()                                          │
│ 6. Check for cancellation again                                      │
│ 7. Update CrawlJob with results                                      │
│ 8. Update Source statistics                                          │
└────────┬────────────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │         │
 Success    Failure
    │         │
    ▼         ▼
┌─────────┐  ┌─────────────┐
│ Return  │  │ Retry or    │
│ result  │  │ mark failed │
└─────────┘  └─────────────┘
```

### 3.3 Multi-Source Crawl Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Multi-Source Crawl Flow                           │
└─────────────────────────────────────────────────────────────────────┘

API: POST /api/sources/crawl-all/
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Create Parent CrawlJob (source=null)                                │
│ Create CrawlJobSourceResult for each source                         │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Dispatch crawl_source for each source                               │
│ with parent_job_id                                                   │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Parallel Execution                               │
├─────────────────────────────────────────────────────────────────────┤
│  Worker 1: crawl_source(source_1, parent_job_id)                    │
│  Worker 2: crawl_source(source_2, parent_job_id)                    │
│  Worker 3: crawl_source(source_3, parent_job_id)                    │
│  Worker 4: crawl_source(source_4, parent_job_id)                    │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼ (each worker on completion)
┌─────────────────────────────────────────────────────────────────────┐
│ _finalize_parent_job(parent_job_id)                                 │
│   - Update CrawlJobSourceResult                                      │
│   - Aggregate totals to parent CrawlJob                              │
│   - Check if all sources complete                                    │
│   - Mark parent as completed/failed                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Article Processing Pipeline

### 4.1 Full Processing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Article Processing Pipeline                        │
└─────────────────────────────────────────────────────────────────────┘

Trigger: AUTO_PROCESS_ARTICLES=True after crawl
     or: POST /api/articles/{id}/reprocess/
     or: Celery Beat schedule
         │
         ▼
┌─────────────────┐
│ Dispatch task   │ ← process_article_pipeline.delay(article_id)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 1: Extraction                               │
├─────────────────────────────────────────────────────────────────────┤
│ Status: collected → extracting                                      │
│ Action: ArticleExtractor().extract(article)                         │
│   - Fetch HTML if not present                                        │
│   - Parse with newspaper3k / trafilatura                            │
│   - Extract text, metadata, language                                 │
│ Status: extracting → extracted                                       │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 2: Translation                              │
├─────────────────────────────────────────────────────────────────────┤
│ Condition: article.original_language != 'en'                        │
│ Status: extracted → translating                                     │
│ Action: ArticleTranslator().translate_article(article)              │
│   - Call Google Translate API                                        │
│   - Store in content_translated                                      │
│ Status: translating → translated                                     │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 3: Scoring                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Status: translated → scoring                                        │
│ Action: ArticleScorer().score_article(article)                      │
│   - Calculate relevance_score                                        │
│   - Calculate timeliness_score                                       │
│   - Calculate source_reputation_score                                │
│   - Calculate content_depth_score                                    │
│   - Calculate uniqueness_score                                       │
│   - Compute weighted total_score                                     │
│   - Assign quality_category                                          │
│ Status: scoring → scored                                             │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 4: Finalization                             │
├─────────────────────────────────────────────────────────────────────┤
│ Status: scored → completed                                          │
│ Action: Mark article as fully processed                              │
│ Available for: Content opportunity analysis                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Content Generation Flow

### 5.1 Opportunity Detection Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Opportunity Detection Flow                          │
└─────────────────────────────────────────────────────────────────────┘

Trigger: GET /api/content/opportunities/generate/
     or: POST /api/content/opportunities/batches/
     or: Celery Beat schedule
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 1: Article Selection                        │
├─────────────────────────────────────────────────────────────────────┤
│ Filter articles:                                                     │
│   - processing_status = 'completed'                                  │
│   - collected_at > (now - max_age_days)                             │
│   - total_score >= min_score                                         │
│   - Optional: topic, region filters                                  │
│ Order by: -total_score                                               │
│ Limit: param.limit (default 10)                                     │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 2: LLM Analysis                             │
├─────────────────────────────────────────────────────────────────────┤
│ If Claude available:                                                 │
│   - Build opportunity prompt with article summaries                  │
│   - Call Claude API                                                  │
│   - Parse JSON response                                              │
│   - Extract opportunities                                            │
│ Else:                                                                │
│   - Run heuristic analysis                                           │
│   - Trending topics (high frequency)                                 │
│   - High-score deep dives                                            │
│   - Regional roundups                                                │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 3: Gap Analysis                             │
├─────────────────────────────────────────────────────────────────────┤
│ If include_gaps=True:                                                │
│   - Check coverage of target topics                                  │
│   - Check coverage of target regions                                 │
│   - Generate gap opportunities for underrepresented                  │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 4: Persistence                              │
├─────────────────────────────────────────────────────────────────────┤
│ If save=True:                                                        │
│   - Create ContentOpportunity records                                │
│   - Link source articles (M2M)                                       │
│   - Set status='detected'                                            │
│   - Calculate expires_at                                             │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Return results  │ ← {"opportunities": [...], "articles_analyzed": N}
└─────────────────┘
```

### 5.2 Draft Generation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Draft Generation Flow                             │
└─────────────────────────────────────────────────────────────────────┘

Trigger: POST /api/content/drafts/generate/
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 1: Article Loading                          │
├─────────────────────────────────────────────────────────────────────┤
│ Load articles from article_ids                                       │
│ Or load from opportunity.source_articles                             │
│ Validate: at least 1 article required                                │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 2: Template Selection                       │
├─────────────────────────────────────────────────────────────────────┤
│ If template_id provided:                                             │
│   - Load SynthesisTemplate                                           │
│   - Use custom prompt_template                                       │
│ Else:                                                                │
│   - Use default prompts from CONTENT_TYPE_CONFIG                     │
│   - Apply VOICE_PROMPTS                                              │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 3: Content Generation                       │
├─────────────────────────────────────────────────────────────────────┤
│ If Claude available:                                                 │
│   - Build system prompt (voice, instructions)                        │
│   - Build user prompt (articles, requirements)                       │
│   - Call Claude API                                                  │
│   - Parse JSON response                                              │
│ Else:                                                                │
│   - Generate fallback draft from article excerpts                    │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 4: Quality Assessment                       │
├─────────────────────────────────────────────────────────────────────┤
│ Calculate quality_score:                                             │
│   - Structure (headings, paragraphs)                                 │
│   - Length (vs target)                                               │
│   - Coherence                                                        │
│ Calculate originality_score:                                         │
│   - Vs source article text                                           │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Step 5: Persistence                              │
├─────────────────────────────────────────────────────────────────────┤
│ If save=True:                                                        │
│   - Create ContentDraft record                                       │
│   - Link source articles (M2M)                                       │
│   - Link opportunity (if provided)                                   │
│   - Set status='generated'                                           │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Return draft    │ ← {"title": "...", "content": "...", ...}
└─────────────────┘
```

---

## 6. Scheduled Task Execution

### 6.1 Celery Beat Schedule

```python
# Default periodic tasks (configurable via django-celery-beat admin)

SCHEDULED_TASKS = {
    'crawl-active-sources-hourly': {
        'task': 'apps.sources.tasks.crawl_active_sources',
        'schedule': crontab(minute=0),  # Every hour
    },
    'expire-old-opportunities': {
        'task': 'apps.content.tasks.expire_old_opportunities',
        'schedule': crontab(minute=30),  # Every hour at :30
    },
    'cleanup-old-crawl-jobs': {
        'task': 'apps.sources.tasks.cleanup_old_jobs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}
```

### 6.2 Beat Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Celery Beat Execution                           │
└─────────────────────────────────────────────────────────────────────┘

Every tick (typically 1 second):
         │
         ▼
┌─────────────────┐
│ Check schedules │ ← Query PeriodicTask table
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Find due tasks  │ ← Compare last_run_at with schedule
└────────┬────────┘
         │
         ▼
For each due task:
         │
         ▼
┌─────────────────┐
│ Submit to queue │ ← Apply routing from CELERY_TASK_ROUTES
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Update last_run │ ← Set last_run_at = now
└─────────────────┘
```

---

## 7. Error Handling Flow

### 7.1 Task Error Recovery

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Task Error Recovery                              │
└─────────────────────────────────────────────────────────────────────┘

Task execution raises exception:
         │
         ▼
┌─────────────────┐
│ Check retries   │ ← self.request.retries < max_retries?
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
 Can retry   Max retries
    │         │
    ▼         ▼
┌─────────┐  ┌─────────────────┐
│ Retry   │  │ Mark as failed  │
│ task    │  │ Log error       │
└────┬────┘  │ Update model    │
     │       └─────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Calculate countdown: 60 * (2 ** retries)                            │
│   Attempt 1: 60 seconds                                              │
│   Attempt 2: 120 seconds                                             │
│   Attempt 3: 240 seconds                                             │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Re-queue task   │ ← With ETA = now + countdown
└─────────────────┘
```

### 7.2 API Error Response

```
┌─────────────────────────────────────────────────────────────────────┐
│                    API Error Response                               │
└─────────────────────────────────────────────────────────────────────┘

Exception raised in view:
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ custom_exception_handler(exc, context)                              │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Get request_id from context                                       │
│ 2. Log exception with request_id                                     │
│ 3. Map exception to HTTP status                                      │
│ 4. Build structured response                                         │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ▼
Response:
{
    "detail": "Article not found",
    "code": "not_found",
    "request_id": "a1b2c3d4-..."
}
HTTP 404 Not Found
X-Request-ID: a1b2c3d4-...
```

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
