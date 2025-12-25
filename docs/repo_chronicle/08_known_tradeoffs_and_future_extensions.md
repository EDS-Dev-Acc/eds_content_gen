# 08 Known Tradeoffs and Future Extensions

> **Purpose**: Document known technical debt, design decisions with tradeoffs, limitations, and planned future improvements.

---

## 1. Design Decisions and Rationale

### 1.1 Monolith Over Microservices

**Decision**: Single Django monolith with Celery workers

**Rationale**:
- Simpler deployment and operations
- Shared database transactions
- Easier debugging and testing
- Lower infrastructure cost
- Appropriate for current scale

**Tradeoff**:
- Limited independent scaling per component
- Single codebase deployment
- Shared failure domain

**Future Path**: Consider service extraction when:
- Crawling needs independent scaling (10x+ sources)
- LLM processing becomes bottleneck
- Team size exceeds 10+ developers

### 1.2 UUID Primary Keys

**Decision**: UUIDs for all model primary keys

**Rationale**:
- Globally unique identifiers
- Safe for distributed systems
- No enumeration attacks
- Merge-friendly across environments

**Tradeoff**:
- Larger storage (16 bytes vs 4 bytes)
- Slower index operations
- Less readable in logs

**Mitigation**: Index optimization, proper database tuning

### 1.3 JSON Fields for Flexible Schema

**Decision**: JSONField for `metadata`, `crawler_config`, `preferences`

**Rationale**:
- Schema flexibility for evolving requirements
- Avoid frequent migrations
- Store heterogeneous data

**Tradeoff**:
- No database-level validation
- Harder to query efficiently
- Potential for data drift

**Mitigation**: Application-level validation, documented schemas

### 1.4 Synchronous LLM Calls in Tasks

**Decision**: LLM API calls within Celery tasks (blocking)

**Rationale**:
- Simpler error handling
- Natural retry mechanism
- Task-level timeout management

**Tradeoff**:
- Worker blocked during API calls
- Limited throughput per worker
- Timeout complexity

**Future Path**: Consider async LLM client if throughput insufficient

---

## 1.5 Capture-First Discovery Architecture (Phase 16)

**Decision**: Store raw HTTP responses before classification

**Rationale**:
- Complete auditability of discovery process
- Zero re-fetches during manual review
- Reproducible classification experiments
- Content hash deduplication

**Tradeoff**:
- Increased storage requirements
- Additional database writes per discovery
- File cleanup maintenance required

**Mitigation**: 
- Gzip compression (6x size reduction typical)
- TTL-based cleanup (30-day default)
- Inline storage for small responses (<50KB)
- Hash-based deduplication prevents redundant storage

### 1.6 Synchronous CLI Fallback (Phase 16)

**Decision**: `manage.py run_discovery` supports sync mode without Celery

**Rationale**:
- Works without Redis/Celery infrastructure
- Simpler debugging and testing
- Suitable for manual one-off runs
- No worker dependencies

**Tradeoff**:
- Blocks terminal during execution
- No progress visibility in console UI
- Cannot be cancelled mid-run easily

**Future Path**: Add async mode with background execution when Celery available

### 1.7 Weighted Multi-Dimensional Scoring (Phase 16)

**Decision**: Four-dimension scoring with configurable weights

**Rationale**:
- Separates concerns (relevance vs utility vs freshness vs authority)
- Transparent scoring logic
- Adjustable emphasis per dimension
- Supports diverse seed quality criteria

**Tradeoff**:
- Requires calibration for optimal weights
- More fields to maintain
- Scoring logic must be kept consistent

**Default Weights**:
```python
SEED_SCORING_WEIGHTS = {
    'relevance': 0.35,  # Topical match
    'utility': 0.25,    # Scrape potential
    'freshness': 0.20,  # Recent activity
    'authority': 0.20,  # Source reputation
}
```

---

## 2. Known Technical Debt

### 2.1 Hard-Coded Prompt Templates

**Issue**: Prompt templates embedded in Python code

**Location**: `apps/content/opportunity.py`, `apps/content/synthesis.py`

**Impact**:
- Requires code deployment to update prompts
- No A/B testing of prompts
- Limited non-developer access

**Proposed Fix**:
```python
# Move to database-backed templates
class PromptTemplate(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)  # 'opportunity', 'draft'
    template = models.TextField()
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
```

**Priority**: Medium

### 2.2 Limited Test Coverage for Crawlers

**Issue**: Crawler implementations lack comprehensive test coverage

**Location**: `apps/sources/crawlers/`

**Impact**:
- Difficult to verify crawler behavior
- Regressions possible on updates
- Hard to add new crawler types

**Proposed Fix**:
- Mock HTTP responses for unit tests
- Integration tests with test fixtures
- Crawler validation suite

**Priority**: High

### 2.3 Missing Database Indexes

**Issue**: Some query patterns lack optimal indexes

**Identified**:
- `Article.collected_at` filtering
- `ContentOpportunity.expires_at` for expiration
- Composite index on `CrawlJob(source_id, status)`

**Impact**: Slow queries at scale

**Proposed Fix**:
```python
class Meta:
    indexes = [
        models.Index(fields=['collected_at']),
        models.Index(fields=['source_id', 'status']),
        models.Index(fields=['expires_at', 'status']),
    ]
```

**Priority**: Medium (add during Phase 15)

### 2.4 No Request Rate Limiting on External APIs

**Issue**: LLM and Translation API calls not rate-limited

**Location**: `apps/content/llm.py`, `apps/articles/services.py`

**Impact**:
- Potential API quota exhaustion
- Cost overruns
- 429 errors under load

**Proposed Fix**:
```python
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=50, period=60)
def _run_prompt(self, ...):
    # Rate-limited API call
```

**Priority**: High

### 2.5 Incomplete Error Classification

**Issue**: Errors not categorized by recoverability

**Location**: Throughout task implementations

**Impact**:
- Retrying non-recoverable errors
- Wasted compute on permanent failures
- Confusing error logs

**Proposed Fix**:
```python
class RecoverableError(Exception):
    """Errors that should trigger retry."""
    pass

class PermanentError(Exception):
    """Errors that should not retry."""
    pass

# In task
try:
    # operation
except RecoverableError as exc:
    raise self.retry(exc=exc)
except PermanentError:
    # Mark failed, don't retry
```

**Priority**: Medium

---

## 3. Current Limitations

### 3.1 Single LLM Provider

**Limitation**: Only Claude (Anthropic) supported

**Impact**:
- Single point of failure
- No cost optimization across providers
- No model comparison

**Future Extension**:
```python
class LLMRouter:
    providers = {
        'anthropic': ClaudeClient,
        'openai': OpenAIClient,
        'google': GeminiClient,
    }
    
    def get_client(self, task_type):
        # Route based on task, cost, availability
        pass
```

### 3.2 No Full-Text Search

**Limitation**: Article search limited to database queries

**Impact**:
- Slow text search at scale
- No semantic search
- Limited filtering options

**Future Extension**:
- Elasticsearch integration
- PostgreSQL full-text search
- Vector embeddings for semantic search

### 3.3 Limited Analytics

**Limitation**: Basic metrics only, no dashboards

**Impact**:
- Manual data analysis required
- No trend visualization
- Limited operational insights

**Future Extension**:
- Prometheus + Grafana dashboards
- Custom analytics app implementation
- BI tool integration

### 3.4 No Content Versioning

**Limitation**: Drafts have basic version tracking

**Impact**:
- Cannot compare draft versions
- No rollback capability
- Limited edit history

**Future Extension**:
```python
class DraftVersion(BaseModel):
    draft = models.ForeignKey(ContentDraft)
    version = models.IntegerField()
    content = models.TextField()
    created_by = models.ForeignKey(User)
    diff_from_previous = models.TextField()
```

### 3.5 Manual Source Discovery

**Limitation**: Sources added manually

**Impact**:
- Slow source expansion
- No automated discovery
- Missing emerging sources

**Status**: **ADDRESSED IN PHASE 16**

Phase 16 implements automated seed discovery with:
- Multi-channel connectors (SERP, sitemap, RSS, API)
- Query generation from target briefs
- LLM-assisted classification
- Review queue for human validation

---

## 3.6 Phase 16 Known Limitations

### 3.6.1 SERP Connector Stub

**Limitation**: SERP API connector is stub implementation

**Impact**:
- No real search results in discovery
- Must use mock data or implement provider

**Future Extension**:
- Integrate with SerpAPI, Serper.dev, or Google Custom Search
- Add API key configuration
- Implement result parsing

### 3.6.2 No feedparser Dependency

**Limitation**: RSS connector uses basic XML parsing

**Impact**:
- May not handle all RSS/Atom variations
- No podcast feed support
- Limited error recovery

**Future Extension**:
- Add feedparser to requirements when needed
- Expand format support

### 3.6.3 Single-Threaded Discovery

**Limitation**: CLI discovery runs sequentially

**Impact**:
- Slow for large query sets
- No parallel fetching

**Future Extension**:
- Add concurrent.futures for parallel fetches
- Celery chord for distributed discovery

---

## 4. Performance Considerations

### 4.1 Database Connection Pooling

**Current**: Django default connection handling

**Recommendation**: Add pgBouncer for production
```yaml
# docker-compose.yml
pgbouncer:
  image: edoburu/pgbouncer
  environment:
    - DATABASE_URL=postgres://...
    - POOL_MODE=transaction
    - MAX_CLIENT_CONN=1000
```

### 4.2 Celery Worker Scaling

**Current**: Fixed worker counts per queue

**Recommendation**: Auto-scaling based on queue depth
```python
# Celery autoscaling
celery -A config worker --autoscale=10,2 -Q crawl
```

### 4.3 LLM Response Caching

**Current**: Basic prompt-based caching

**Recommendation**: Redis-backed distributed cache
```python
CACHES = {
    'llm_responses': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'TIMEOUT': 86400,  # 24 hours
    }
}
```

### 4.4 Article Processing Batching

**Current**: Single article per task

**Recommendation**: Batch processing for efficiency
```python
@shared_task
def process_article_batch(article_ids):
    articles = Article.objects.filter(id__in=article_ids)
    for article in articles:
        # Process in single transaction
        pass
```

---

## 5. Security Improvements Needed

### 5.1 API Key Rotation Support

**Gap**: No automated key rotation

**Risk**: Long-lived credentials, manual rotation

**Recommendation**:
- Integration with secrets manager
- Automated rotation schedules
- Zero-downtime rotation procedure

### 5.2 Audit Logging

**Gap**: Limited action audit trail

**Risk**: Compliance, debugging difficulties

**Recommendation**:
```python
class AuditLog(BaseModel):
    user = models.ForeignKey(User)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    resource_id = models.UUIDField()
    details = models.JSONField()
    ip_address = models.GenericIPAddressField()
```

### 5.3 Content Security Policy

**Gap**: No CSP headers configured

**Risk**: XSS vulnerabilities if web UI added

**Recommendation**:
```python
# In production settings
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
```

---

## 6. Future Feature Roadmap

### 6.1 Phase 15: Analytics Dashboard

- Grafana dashboard integration
- Custom metrics endpoints
- Source health monitoring
- Content quality trends

### 6.2 Phase 16: Seed Discovery Architecture ✅ COMPLETED

- **Multi-channel connectors**: SERP, sitemap, RSS, API stubs
- **Query generation**: LLM-assisted query generation from target briefs
- **Capture-first storage**: SeedRawCapture with gzip compression
- **Classification pipeline**: URL normalization, scoring, seed creation
- **Weighted scoring**: Four-dimension scoring (relevance, utility, freshness, authority)
- **Console UI**: Review queue with HTMX partials and modals
- **CLI fallback**: `manage.py run_discovery` for sync execution
- **DiscoveryRun tracking**: Session-based grouping of captures and seeds
- **Session 31 Enhancements**:
  - `lifecycle_status` property for canonical status mapping
  - `discovery_method` property for provenance tracking
  - `request_headers`, `content_length`, `truncated` fields on SeedRawCapture
  - Status alignment helpers (`sync_lifecycle_to_status()`)

### 6.3 Phase 17: Multi-tenant Support

- Organization model
- Per-tenant source isolation
- Usage quotas and billing
- API key per tenant

### 6.4 Phase 18: Advanced NLP

- Named entity extraction
- Sentiment analysis
- Topic modeling
- Event detection

### 6.5 Phase 19: Publishing Integration

- WordPress connector
- CMS webhook notifications
- Publishing workflow
- Scheduled publishing

### 6.6 Phase 20: AI Enhancement

- Multi-model routing
- Fine-tuned models for specific tasks
- Embedding-based search
- Automated quality improvement

### 6.7 Phase 21: Discovery Enhancements

- SERP API provider integration (SerpAPI, Serper.dev)
- Parallel discovery execution
- Automatic re-discovery scheduling
- Discovery quality metrics
- Source recommendation engine

---

## 7. Migration Complexity Notes

### 7.1 High-Risk Migrations

| Migration | Risk | Mitigation |
|-----------|------|------------|
| Add NOT NULL column | Data loss | Default value, backfill first |
| Remove column | Breaking change | Deprecate, remove after cleanup |
| Rename column | API breakage | Add new, migrate, remove old |
| Add unique constraint | Constraint violation | Clean data first |

### 7.2 Migration Best Practices

1. Always backup before migration
2. Test on production-like data
3. Use `--fake` for failed migrations
4. Deploy in maintenance window for large tables
5. Monitor query performance after

---

## 8. Deprecation Schedule

### 8.1 Currently Deprecated

| Feature | Deprecated | Removal Target | Replacement |
|---------|------------|----------------|-------------|
| Legacy crawler API | Session 20 | Phase 16 | New crawler registry |
| Direct source.crawl() | Session 22 | Phase 15 | CrawlJob-based flow |

### 8.2 Planned Deprecations

| Feature | Target Deprecation | Reason |
|---------|-------------------|--------|
| SQLite support | Phase 16 | Production-only PostgreSQL |
| Basic auth | Phase 15 | JWT-only authentication |

---

## 9. Known Issues and Workarounds

### 9.1 Newspaper3k Installation Issues

**Issue**: Compilation errors on some platforms

**Workaround**:
```bash
# Install system dependencies first
apt-get install python3-dev libxml2-dev libxslt1-dev

# Or use pre-built wheel
pip install newspaper3k --prefer-binary
```

### 9.2 Redis Connection Timeouts

**Issue**: Intermittent connection failures

**Workaround**:
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10
```

### 9.3 LLM Token Limit Exceeded

**Issue**: Long articles exceed context window

**Workaround**:
```python
# Truncate content before sending
from apps.content.token_utils import truncate_to_tokens
content = truncate_to_tokens(article.extracted_text, max_tokens=50000)
```

---

## 10. Monitoring Recommendations

### 10.1 Key Metrics to Track

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| Crawl error rate | > 10% | Check source health |
| Processing queue depth | > 1000 | Scale workers |
| LLM API latency | > 30s | Check rate limits |
| Database connections | > 80% | Scale connection pool |
| Failed tasks/hour | > 100 | Investigate patterns |

### 10.2 Log Aggregation

Recommended tools:
- **ELK Stack**: Elasticsearch, Logstash, Kibana
- **Loki + Grafana**: Lightweight alternative
- **CloudWatch**: AWS environments

### 10.3 Alerting

Configure alerts for:
- Service downtime
- Error rate spikes
- Queue backlogs
- API quota approaching
- Database disk usage

---

**Document Version**: 2.1.0  
**Last Updated**: Session 31 (Phase 16 Enhancements)  
**Maintainer**: EMCIP Development Team
