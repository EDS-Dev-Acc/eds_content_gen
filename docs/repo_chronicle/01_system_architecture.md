# 01 System Architecture

> **Purpose**: Comprehensive technical architecture documentation covering all system components, their interactions, and design decisions.

---

## 1. Architecture Overview

EMCIP follows a **layered monolith architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Presentation Layer                          │
│                    (Django REST Framework APIs)                     │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────┐
│                         Application Layer                           │
│              (Django Apps: sources, articles, content, etc.)        │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────┐
│                          Service Layer                              │
│        (Business Logic: Crawlers, Extractors, LLM Clients)         │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────┐
│                           Data Layer                                │
│                    (Django ORM → PostgreSQL/SQLite)                 │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────┐
│                      Infrastructure Layer                           │
│               (Celery, Redis, External APIs, Storage)               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Architecture

### 2.1 Django Applications

The system is organized into 7 Django applications, each with a single responsibility:

```
apps/
├── core/           # Shared base classes, utilities, security
├── sources/        # News source management and crawlers
├── seeds/          # URL candidate discovery and validation
├── articles/       # Article processing pipeline
├── content/        # Opportunity detection and draft synthesis
├── workflows/      # Orchestration logic (reserved for future)
└── analytics/      # Metrics and reporting (reserved for future)
```

### 2.2 Application Dependencies

```
                    ┌────────────┐
                    │    core    │
                    └──────┬─────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────┴─────┐      ┌──────┴─────┐      ┌──────┴─────┐
│  sources   │      │   seeds    │      │  articles  │
└──────┬─────┘      └──────┬─────┘      └──────┬─────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────┴─────┐
                    │  content   │
                    └────────────┘
```

**Dependency Rules**:
- `core` has no dependencies on other apps
- `sources`, `seeds`, `articles` depend on `core`
- `content` depends on `articles` (for article data)
- No circular dependencies allowed

---

## 3. Data Flow Architecture

### 3.1 Primary Data Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Sources  │───►│ Crawlers │───►│  Seeds   │───►│ Articles │───►│ Content  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
 Configure       Fetch HTML      Validate      Process:         Analyze:
 Sources         Create Seeds    Promote to    - Extract        - Opportunities
 Schedule        or Articles     Articles      - Translate      - Drafts
 Crawls                                        - Score          - Templates
```

### 3.2 Article Processing Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  collected  │────►│  extracted  │────►│ translated  │────►│   scored    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                    │
                           ┌────────────────────────────────────────┘
                           ▼
                    ┌─────────────┐
                    │  completed  │
                    └─────────────┘
```

Each transition:
1. **collected → extracted**: Text extraction from HTML via Trafilatura/Newspaper3k
2. **extracted → translated**: Non-English content translated to English
3. **translated → scored**: Quality scoring (relevance, timeliness, source reputation)
4. **scored → completed**: Final state, ready for content opportunities

---

## 4. Async Processing Architecture

### 4.1 Celery Task Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Celery Beat                                │
│                    (Periodic Task Scheduler)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Schedules tasks
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Redis Broker                               │
│                      (Message Queue Backend)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Distributes tasks
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  crawl queue  │       │ process queue │       │ content queue │
│   (4 workers) │       │  (2 workers)  │       │  (2 workers)  │
└───────────────┘       └───────────────┘       └───────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
  crawl_source           extract_text           generate_ops
  validate_seed          translate              generate_draft
  discover_seeds         score_article          expire_opps
```

### 4.2 Task Routing Configuration

```python
CELERY_TASK_ROUTES = {
    'apps.sources.tasks.crawl_source': {'queue': 'crawl'},
    'apps.sources.tasks.validate_seed': {'queue': 'crawl'},
    'apps.seeds.tasks.*': {'queue': 'crawl'},
    'apps.articles.tasks.extract_*': {'queue': 'process'},
    'apps.articles.tasks.translate_*': {'queue': 'process'},
    'apps.articles.tasks.score_*': {'queue': 'process'},
    'apps.content.tasks.*': {'queue': 'content'},
}
```

### 4.3 Task Retry Strategy

All tasks implement exponential backoff:

```python
@shared_task(bind=True, max_retries=3)
def my_task(self, arg):
    try:
        # Task logic
        pass
    except TransientError as exc:
        # Retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

---

## 5. API Architecture

### 5.1 URL Structure

```
/api/
├── auth/                    # JWT authentication
│   ├── token/              # POST - obtain token pair
│   ├── token/refresh/      # POST - refresh access token
│   └── token/verify/       # POST - verify token
├── sources/                 # Source management
│   ├── /                   # GET, POST
│   ├── {id}/               # GET, PUT, PATCH, DELETE
│   ├── {id}/test/          # POST - test crawl
│   └── {id}/crawl-now/     # POST - trigger full crawl
├── seeds/                   # Seed management
│   ├── /                   # GET, POST
│   ├── {id}/               # GET, PUT, PATCH, DELETE
│   └── import/             # POST - bulk import
├── articles/                # Article management
│   ├── /                   # GET, POST
│   ├── {id}/               # GET, PUT, PATCH, DELETE
│   └── {id}/reprocess/     # POST - trigger reprocessing
├── content/
│   ├── opportunities/      # GET, POST - opportunity CRUD
│   ├── drafts/             # GET, POST - draft CRUD
│   └── templates/          # GET, POST - template management
├── exports/                 # Export management
│   ├── /                   # GET, POST
│   └── {id}/download/      # GET - download file
└── settings/
    └── llm/                # GET, PATCH - LLM configuration
```

### 5.2 Authentication Flow

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  Client  │────────►│   API    │────────►│   JWT    │
└──────────┘         └──────────┘         └──────────┘
     │                    │                     │
     │ POST /auth/token/  │                     │
     │ {username, pass}   │                     │
     │───────────────────►│                     │
     │                    │ Validate credentials│
     │                    │────────────────────►│
     │                    │                     │
     │                    │◄────────────────────│
     │                    │ {access, refresh}   │
     │◄───────────────────│                     │
     │                    │                     │
     │ GET /api/sources/  │                     │
     │ Authorization:     │                     │
     │ Bearer {access}    │                     │
     │───────────────────►│                     │
     │                    │ Verify token        │
     │                    │────────────────────►│
     │                    │                     │
     │◄───────────────────│                     │
     │ {sources: [...]}   │                     │
```

### 5.3 Error Handling

Custom exception handler provides consistent error responses:

```python
# config/settings/base.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'apps.core.exceptions.emcip_exception_handler',
}

# Response format
{
    "detail": "Human-readable error message",
    "code": "error_code",
    "request_id": "uuid-for-tracing"
}
```

---

## 6. External Service Integration

### 6.1 LLM Integration (Claude)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         ClaudeClient                                 │
│                    (apps/content/llm.py)                            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ Token Counter │       │Response Cache │       │ Cost Tracker  │
│ (estimate,    │       │ (LRU cache    │       │ (usage stats, │
│  truncate)    │       │  for prompts) │       │  budgets)     │
└───────────────┘       └───────────────┘       └───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Anthropic API        │
                    │  (api.anthropic.com)  │
                    └───────────────────────┘
```

**Features**:
- Prompt template registry for reusable prompts
- Response caching to avoid duplicate API calls
- Cost tracking for budget management
- Automatic retry with exponential backoff

### 6.2 Translation Service

```
┌───────────────────────────────────────────────────────────────┐
│                   ArticleTranslator                           │
│               (apps/articles/services.py)                     │
└───────────────────────────┬───────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌───────────────┐               ┌───────────────┐
    │ Google Trans  │               │  Fallback:    │
    │ API (primary) │               │  Copy original│
    └───────────────┘               └───────────────┘
```

### 6.3 Content Extraction

```
┌───────────────────────────────────────────────────────────────┐
│                 HybridContentExtractor                        │
│            (apps/sources/crawlers/extractors.py)              │
└───────────────────────────┬───────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌───────────────┐               ┌───────────────┐
    │  Trafilatura  │               │  Newspaper3k  │
    │  (preferred)  │               │  (fallback)   │
    └───────────────┘               └───────────────┘
```

---

## 7. Security Architecture

### 7.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Security Perimeter                             │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 1: Network Security                                           │
│   - HTTPS only (TLS 1.3)                                           │
│   - CORS restrictions                                               │
│   - Rate limiting at load balancer                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2: Authentication                                             │
│   - JWT tokens with short expiry (5 min access, 24h refresh)       │
│   - Token blacklisting on logout                                    │
│   - Password hashing (PBKDF2)                                       │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3: Authorization                                              │
│   - Role-based access (admin, operator, viewer)                     │
│   - Object-level permissions                                        │
│   - Django admin restrictions                                       │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 4: Application Security                                       │
│   - SSRF protection (HTTPFetcher)                                   │
│   - Input validation                                                │
│   - SQL injection prevention (Django ORM)                           │
│   - XSS protection (DRF serializers)                                │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 5: Throttling                                                 │
│   - Per-user rate limits                                            │
│   - Per-endpoint burst limits                                       │
│   - Anonymous rate limiting                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 SSRF Protection

All external HTTP requests must use the secure fetcher:

```python
# apps/core/security.py
class HTTPFetcher:
    BLOCKED_NETWORKS = [
        '10.0.0.0/8',      # Private
        '172.16.0.0/12',   # Private
        '192.168.0.0/16',  # Private
        '127.0.0.0/8',     # Loopback
        '169.254.0.0/16',  # Link-local
    ]
    
    @classmethod
    def fetch(cls, url: str, **kwargs) -> requests.Response:
        # Validate URL is not internal
        # Resolve DNS and check IP
        # Block private network access
        pass
```

---

## 8. Observability Architecture

### 8.1 Tracing

```
┌─────────────────────────────────────────────────────────────────────┐
│                      OpenTelemetry SDK                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ Django        │       │ Celery        │       │ HTTP Requests │
│ Middleware    │       │ Signals       │       │ Instrumented  │
└───────────────┘       └───────────────┘       └───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Trace Exporter      │
                    │   (Jaeger/Tempo)      │
                    └───────────────────────┘
```

### 8.2 Metrics

```python
# Prometheus metrics exposed at /metrics
from apps.core.metrics import (
    articles_processed_total,      # Counter
    crawl_duration_seconds,        # Histogram
    active_crawl_jobs,             # Gauge
    llm_tokens_used_total,         # Counter
)
```

### 8.3 Request ID Tracking

```python
# Middleware adds request ID to all requests
class RequestIDMiddleware:
    def __call__(self, request):
        request_id = request.headers.get('X-Request-ID', uuid4())
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response
```

---

## 9. Scalability Considerations

### 9.1 Horizontal Scaling Points

| Component | Scaling Method | Bottleneck |
|-----------|----------------|------------|
| Web servers | Add Gunicorn instances | CPU/Memory |
| Celery workers | Add workers per queue | I/O, External APIs |
| Redis | Redis Cluster | Memory |
| PostgreSQL | Read replicas | Connection count |

### 9.2 Caching Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Cache Layers                                  │
├─────────────────────────────────────────────────────────────────────┤
│ L1: Application Cache (Django cache framework)                      │
│     - Session data                                                  │
│     - View-level caching                                            │
│     - TTL: 5-15 minutes                                             │
├─────────────────────────────────────────────────────────────────────┤
│ L2: LLM Response Cache                                              │
│     - Cached by prompt hash                                         │
│     - TTL: 24 hours                                                 │
│     - Reduces API costs                                             │
├─────────────────────────────────────────────────────────────────────┤
│ L3: Database Query Cache                                            │
│     - PostgreSQL query cache                                        │
│     - Connection pooling (pgBouncer)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. Deployment Architecture

### 10.1 Docker Compose Stack

```yaml
services:
  web:
    build: .
    command: gunicorn config.wsgi:application
    ports: ["8000:8000"]
    depends_on: [db, redis]
    
  celery-worker:
    build: .
    command: celery -A config worker -l INFO
    depends_on: [db, redis]
    
  celery-beat:
    build: .
    command: celery -A config beat -l INFO
    depends_on: [db, redis]
    
  db:
    image: postgres:15
    volumes: [postgres_data:/var/lib/postgresql/data]
    
  redis:
    image: redis:7
    volumes: [redis_data:/data]
```

### 10.2 Production Recommendations

| Component | Configuration |
|-----------|---------------|
| Gunicorn workers | `2 * CPU_CORES + 1` |
| Celery crawl workers | 4 (I/O bound) |
| Celery process workers | 2 (CPU bound) |
| PostgreSQL connections | 100 max |
| Redis memory | 2GB minimum |

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
