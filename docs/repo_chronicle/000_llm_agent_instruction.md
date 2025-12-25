# 000 LLM Agent Instruction for EMCIP

> **Purpose**: Provide comprehensive guidance for LLM agents operating on this codebase.

---

## 1. Project Identity

**Name**: EMCIP (Emerging Markets Content Intelligence Platform)  
**Domain**: Automated news aggregation, content synthesis, and intelligence generation for emerging markets  
**Primary Language**: Python 3.11+  
**Framework**: Django 5.0+ with Django REST Framework  
**Task Queue**: Celery 5.3+ with Redis broker  
**Database**: PostgreSQL 15+ (production), SQLite (development)

---

## 2. Critical Constraints

### 2.1 Never Modify Without Understanding

Before modifying any file, ensure you understand:

1. **State machines** - `Article.processing_status` and `CrawlJob.status` have defined transitions
2. **Signal handlers** - Django signals may trigger cascading effects
3. **Celery task chains** - Modifying task return values can break downstream tasks
4. **Migration dependencies** - Never delete or modify applied migrations

### 2.2 Protected Paths

| Path | Reason |
|------|--------|
| `config/settings/base.py` | Core configuration - changes affect entire system |
| `apps/*/migrations/` | Database schema history - never modify applied migrations |
| `apps/core/models.py` | BaseModel used by all apps |
| `apps/core/security.py` | SSRF protection, input validation |

### 2.3 Security Non-Negotiables

1. **SSRF Protection**: All HTTP requests must use `HTTPFetcher.fetch()` from `apps/core/security.py`
2. **Input Validation**: All user inputs must be validated before database operations
3. **No Hardcoded Secrets**: All credentials via environment variables
4. **Rate Limiting**: API endpoints must have throttle classes applied

---

## 3. Architecture Overview

### 3.1 Application Structure

```
EMCIP/
├── config/                 # Django project configuration
│   ├── settings/          # Environment-specific settings
│   ├── celery.py          # Celery app configuration
│   └── urls.py            # URL routing
├── apps/
│   ├── core/              # Shared base models, utilities, security
│   ├── sources/           # News source management & crawlers
│   ├── seeds/             # URL candidate discovery & validation
│   ├── articles/          # Article processing pipeline
│   ├── content/           # Opportunity detection & draft synthesis
│   ├── workflows/         # Orchestration (reserved)
│   └── analytics/         # Metrics & reporting (reserved)
```

### 3.2 Data Flow Pipeline

```
Sources → Crawlers → Seeds → Articles → Processing → Content Opportunities → Drafts
```

1. **Sources**: Configured news sources with domains, crawler configs
2. **Crawlers**: Fetch HTML from sources, create Seeds or Articles
3. **Seeds**: URL candidates validated and promoted to Articles
4. **Articles**: Raw → Extracted → Translated → Scored → Completed
5. **Content**: Opportunities detected, Drafts synthesized via LLM

---

## 4. Key Models and State Machines

### 4.1 Article Processing Status

```python
PROCESSING_STATUSES = [
    'collected',    # Initial state after crawl
    'extracting',   # Text extraction in progress
    'extracted',    # Clean text available
    'translating',  # Translation in progress
    'translated',   # English content ready
    'scoring',      # Quality scoring in progress
    'scored',       # Scores computed
    'completed',    # Fully processed
    'failed',       # Processing error
    'skipped',      # Intentionally not processed
]
```

### 4.2 CrawlJob Status

```python
STATUS_CHOICES = [
    'pending',      # Created, not started
    'running',      # Currently executing
    'completed',    # Successfully finished
    'failed',       # Error occurred
    'cancelled',    # User cancelled
]
```

### 4.3 Seed Status

```python
STATUS_CHOICES = [
    'pending',      # Awaiting validation
    'validating',   # Validation in progress
    'valid',        # Passed validation
    'invalid',      # Failed validation
    'promoted',     # Converted to Article
    'discarded',    # Manually rejected
]
```

---

## 5. Celery Task Guidelines

### 5.1 Task Routing

Tasks are routed to specific queues based on function:

| Queue | Tasks | Concurrency |
|-------|-------|-------------|
| `crawl` | `crawl_source`, `validate_seed` | 4 workers |
| `process` | `extract_article_text`, `translate_article`, `score_article` | 2 workers |
| `content` | `generate_opportunities`, `generate_draft` | 2 workers |
| `default` | Everything else | 1 worker |

### 5.2 Task Patterns

```python
# Always use bind=True for retry access
@shared_task(bind=True, max_retries=3)
def my_task(self, arg1, arg2):
    try:
        # Task logic
        pass
    except ExpectedError as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### 5.3 Cancellation Checks

Long-running tasks must check for cancellation:

```python
# Check parent job status periodically
if parent_job_id:
    parent = CrawlJob.objects.get(id=parent_job_id)
    if parent.status == 'cancelled':
        return {'status': 'skipped', 'reason': 'cancelled'}
```

---

## 6. API Patterns

### 6.1 ViewSet Standard Actions

All ViewSets follow DRF conventions:

| Action | HTTP Method | URL Pattern |
|--------|-------------|-------------|
| list | GET | `/api/{resource}/` |
| create | POST | `/api/{resource}/` |
| retrieve | GET | `/api/{resource}/{id}/` |
| update | PUT | `/api/{resource}/{id}/` |
| partial_update | PATCH | `/api/{resource}/{id}/` |
| destroy | DELETE | `/api/{resource}/{id}/` |

### 6.2 Custom Actions

Use `@action` decorator for custom endpoints:

```python
@action(detail=True, methods=['post'])
def crawl_now(self, request, pk=None):
    """Trigger immediate crawl for a source."""
    source = self.get_object()
    # Implementation
```

### 6.3 Error Response Format

```json
{
    "detail": "Human-readable error message",
    "code": "error_code",
    "errors": {
        "field_name": ["Specific field error"]
    }
}
```

---

## 7. LLM Integration

### 7.1 Claude Client Usage

```python
from apps.content.llm import ClaudeClient, parse_llm_json

client = ClaudeClient()
if client.available:
    response = client._run_prompt(
        prompt="Your prompt here",
        system="System instructions",
        max_tokens=2048,
    )
    data = parse_llm_json(response)
```

### 7.2 Prompt Guidelines

1. **Always request JSON output** with schema specification
2. **Specify "no markdown fences"** in prompts
3. **Use `parse_llm_json()`** to handle fence-wrapped responses
4. **Implement fallback logic** when LLM unavailable

---

## 8. Testing Requirements

### 8.1 Required Test Coverage

All new code must include:

1. **Unit tests** for business logic
2. **Integration tests** for API endpoints
3. **Celery task tests** using `@pytest.mark.celery`

### 8.2 Test Database

Tests use SQLite with `DATABASES['default']` overridden. Never rely on PostgreSQL-specific features in tests.

### 8.3 Mock External Services

```python
@patch.object(ClaudeClient, 'available', False)
def test_without_llm(self):
    # Test fallback behavior
    pass
```

---

## 9. Common Modification Patterns

### 9.1 Adding a New Model Field

1. Add field to model class
2. Create migration: `python manage.py makemigrations`
3. Update serializers
4. Update views if needed
5. Add tests

### 9.2 Adding a New API Endpoint

1. Create ViewSet or View in `views.py`
2. Register in `urls.py`
3. Add serializers if needed
4. Apply throttle classes
5. Add tests

### 9.3 Adding a New Celery Task

1. Define task in `tasks.py` with proper decorators
2. Add to `CELERY_TASK_ROUTES` if needed
3. Register beat schedule if periodic
4. Add tests

---

## 10. Environment Variables

### 10.1 Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Random 50+ chars |
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |
| `DATABASE_URL` | PostgreSQL connection | `postgres://...` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |

### 10.2 Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `False` | Enable debug mode |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Claude model |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `LLM_TEMPERATURE` | `0.7` | Response randomness |

---

## 11. Debugging Tips

### 11.1 Celery Task Issues

```bash
# Monitor tasks
celery -A config inspect active

# Purge stuck tasks
celery -A config purge

# Check flower dashboard
celery -A config flower
```

### 11.2 Database Issues

```python
# Check model state
from apps.articles.models import Article
Article.objects.filter(processing_status='failed').count()

# Reset stuck articles
Article.objects.filter(processing_status='extracting').update(
    processing_status='collected'
)
```

### 11.3 LLM Issues

```python
# Test Claude connectivity
from apps.content.llm import ClaudeClient
client = ClaudeClient()
print(f"Available: {client.available}")
```

---

## 12. Code Style Guidelines

1. **Imports**: Standard library → Django → Third-party → Local apps
2. **Docstrings**: Google style with Args/Returns sections
3. **Type hints**: Required for public methods
4. **Line length**: 88 characters (Black formatter)
5. **Naming**: `snake_case` for functions/variables, `PascalCase` for classes

---

## 13. Before Submitting Changes

1. [ ] Run `python manage.py check` - no errors
2. [ ] Run `python manage.py makemigrations --check` - no changes needed
3. [ ] Run `pytest` - all tests pass
4. [ ] Run `black .` - code formatted
5. [ ] Run `ruff .` - no linting errors
6. [ ] Update documentation if behavior changed

---

## 14. Emergency Rollback Procedures

### 14.1 Database Migration Rollback

```bash
python manage.py migrate app_name previous_migration_number
```

### 14.2 Celery Task Cancellation

```python
from celery import current_app
current_app.control.revoke(task_id, terminate=True)
```

### 14.3 Full System Restart

```bash
# Stop all services
docker-compose down

# Clear Redis
docker-compose exec redis redis-cli FLUSHALL

# Restart
docker-compose up -d
```

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
