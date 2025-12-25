# 04 Data Models and State

> **Purpose**: Complete database schema documentation including all models, fields, relationships, constraints, indexes, and state machine definitions.

---

## 1. Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ OperatorProfile │       │     Source      │       │      Seed       │
│ (core)          │       │   (sources)     │◄──────│    (seeds)      │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │                         │                         │
         │                         ▼                         │
         │                ┌─────────────────┐                │
         │                │    CrawlJob     │                │
         │                │   (sources)     │                │
         │                └────────┬────────┘                │
         │                         │                         │
         │                         │                         │
         │                         ▼                         ▼
         │                ┌─────────────────┐       ┌─────────────────┐
         │                │    Article      │◄──────│  (promoted_     │
         │                │   (articles)    │       │   article)      │
         │                └────────┬────────┘       └─────────────────┘
         │                         │
         │         ┌───────────────┼───────────────┐
         │         │               │               │
         │         ▼               ▼               ▼
         │  ┌────────────┐  ┌────────────┐  ┌────────────┐
         │  │ArticleScore│  │ArticleLLM  │  │ArticleImage│
         │  │ Breakdown  │  │ Artifact   │  │            │
         │  └────────────┘  └────────────┘  └────────────┘
         │
         │                         ▼
         │                ┌─────────────────┐
         │                │  ContentOpp     │
         │                │   ortunity      │
         │                └────────┬────────┘
         │                         │
         │                         ▼
         │                ┌─────────────────┐
         │                │  ContentDraft   │
         │                └────────┬────────┘
         │                         │
         │                         ▼
         │                ┌─────────────────┐
         │                │  DraftFeedback  │
         │                └─────────────────┘
         │
         ▼
┌─────────────────┐
│    ExportJob    │
│   (articles)    │
└─────────────────┘

Phase 16 Discovery Architecture:

┌─────────────────┐
│  DiscoveryRun   │ ◄── Orchestrates discovery session
│    (seeds)      │
└────────┬────────┘
         │ 1:N
         ├────────────────────────┐
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌─────────────────┐
│ SeedRawCapture  │ ──►  │      Seed       │
│    (seeds)      │      │   (extended)    │
└─────────────────┘      └─────────────────┘
  Stores gzipped            Extended with:
  HTTP responses            - scoring fields
                           - provenance
                           - review workflow
```

---

## 2. Core Models

### 2.1 BaseModel (Abstract)

**Location**: `apps/core/models.py`

All models inherit from this abstract base class.

```python
class BaseModel(models.Model):
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Unique identifier |
| `created_at` | DateTime | auto_now_add | Record creation time |
| `updated_at` | DateTime | auto_now | Last modification time |

### 2.2 OperatorProfile

**Location**: `apps/core/models.py`

```python
class OperatorProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    preferences = models.JSONField(default=dict, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `user` | FK → User | OneToOne | Django auth user |
| `role` | Char(20) | choices | 'admin', 'operator', 'viewer' |
| `preferences` | JSON | default={} | User preferences |
| `last_activity` | DateTime | nullable | Last active timestamp |

**Role Permissions**:

| Role | Read | Write | Delete | Admin |
|------|------|-------|--------|-------|
| viewer | ✅ | ❌ | ❌ | ❌ |
| operator | ✅ | ✅ | ❌ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ |

---

## 3. Sources Models

### 3.1 Source

**Location**: `apps/sources/models.py`

```python
class Source(BaseModel):
    # Identity
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=255, unique=True)
    url = models.URLField(max_length=500)
    description = models.TextField(blank=True)
    
    # Classification
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    region = models.CharField(max_length=50, choices=REGIONS)
    language = models.CharField(max_length=10, default='en')
    
    # Crawler config
    crawler_type = models.CharField(max_length=50, default='requests')
    crawler_config = models.JSONField(default=dict, blank=True)
    pagination_state = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=5)  # 1=highest, 10=lowest
    reputation_score = models.IntegerField(default=50)
    
    # Statistics
    total_articles_collected = models.IntegerField(default=0)
    last_crawled_at = models.DateTimeField(null=True)
    last_successful_crawl = models.DateTimeField(null=True)
    crawl_errors_count = models.IntegerField(default=0)
    last_error_message = models.TextField(blank=True)
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | Char(200) | required | Display name |
| `domain` | Char(255) | unique | Domain for dedup |
| `url` | URL(500) | required | Base URL |
| `source_type` | Char(50) | choices | news, blog, wire, etc. |
| `region` | Char(50) | choices | Target region |
| `crawler_type` | Char(50) | default='requests' | Crawler implementation |
| `crawler_config` | JSON | default={} | Crawler settings |
| `pagination_state` | JSON | default={} | Resume state |
| `is_active` | Boolean | default=True | Enabled for crawling |
| `priority` | Integer | default=5 | 1-10, crawl priority |
| `reputation_score` | Integer | default=50 | 0-100, source quality |

**Indexes**:
- `domain` (unique)
- `is_active`
- `region`
- `source_type`

### 3.2 CrawlJob

**Location**: `apps/sources/models.py`

```python
class CrawlJob(BaseModel):
    # Relationships
    source = models.ForeignKey(Source, null=True, on_delete=models.CASCADE)
    parent_job = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)
    
    # Execution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    task_id = models.CharField(max_length=255, blank=True)
    triggered_by = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    config_overrides = models.JSONField(default=dict, blank=True)
    
    # Timing
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    
    # Results
    total_found = models.IntegerField(default=0)
    new_articles = models.IntegerField(default=0)
    duplicates = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    pages_crawled = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
```

| Field | Type | Description |
|-------|------|-------------|
| `source` | FK → Source | Nullable for multi-source jobs |
| `parent_job` | FK → self | Parent for multi-source runs |
| `status` | Char(20) | Job state |
| `task_id` | Char(255) | Celery task ID |
| `triggered_by` | Char(20) | 'schedule', 'api', 'manual' |
| `config_overrides` | JSON | Runtime config |

**State Machine**:

```
                    ┌────────────┐
                    │  pending   │
                    └─────┬──────┘
                          │ start
                          ▼
                    ┌────────────┐
          ┌────────│  running   │────────┐
          │        └────────────┘        │
          │ success                      │ error
          ▼                              ▼
    ┌────────────┐                ┌────────────┐
    │ completed  │                │   failed   │
    └────────────┘                └────────────┘
          
          │ cancel (from pending/running)
          ▼
    ┌────────────┐
    │ cancelled  │
    └────────────┘
```

**Indexes**:
- `status`
- `source_id`
- `started_at` (for date filtering)
- `triggered_by`

### 3.3 CrawlJobSourceResult

**Location**: `apps/sources/models.py`

```python
class CrawlJobSourceResult(BaseModel):
    crawl_job = models.ForeignKey(CrawlJob, on_delete=models.CASCADE)
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    
    articles_found = models.IntegerField(default=0)
    articles_new = models.IntegerField(default=0)
    articles_duplicate = models.IntegerField(default=0)
    pages_crawled = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
```

---

## 4. Seeds Models

### 4.1 Seed

**Location**: `apps/seeds/models.py`

```python
class Seed(BaseModel):
    # Identity
    url = models.URLField(max_length=2048)
    normalized_url = models.CharField(max_length=2048, db_index=True)
    title = models.CharField(max_length=500, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    
    # Relationships
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    promoted_article = models.ForeignKey(
        'articles.Article', null=True, on_delete=models.SET_NULL
    )
    
    # Classification
    seed_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    confidence = models.IntegerField(default=50)
    country = models.CharField(max_length=2, blank=True, db_index=True)
    regions = models.JSONField(default=list, blank=True)
    topics = models.JSONField(default=list, blank=True)
    
    # Timestamps
    discovered_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True)
    promoted_at = models.DateTimeField(null=True)
    
    # Validation
    is_reachable = models.BooleanField(null=True)
    is_crawlable = models.BooleanField(null=True)
    has_articles = models.BooleanField(null=True)
    article_count_estimate = models.IntegerField(null=True)
    validation_errors = models.JSONField(default=list, blank=True)
    
    # Phase 16: Discovery provenance
    query_used = models.CharField(max_length=500, blank=True)
    referrer_url = models.URLField(max_length=2000, blank=True)
    discovery_run_id = models.UUIDField(null=True, blank=True, db_index=True)
    
    # Phase 16: Multi-dimensional scoring
    relevance_score = models.IntegerField(default=0)
    utility_score = models.IntegerField(default=0)
    freshness_score = models.IntegerField(default=0)
    authority_score = models.IntegerField(default=0)
    overall_score = models.IntegerField(default=0, db_index=True)
    
    # Phase 16: Scrape planning hints
    scrape_plan_hint = models.CharField(max_length=50, blank=True)
    recommended_entrypoints = models.JSONField(default=list, blank=True)
    expected_fields = models.JSONField(default=list, blank=True)
    
    # Phase 16: Review workflow
    review_status = models.CharField(max_length=20, default='pending', db_index=True)
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    
    priority = models.IntegerField(default=5)
```

| Field | Type | Description |
|-------|------|-------------|
| `url` | URL(2048) | Original URL |
| `normalized_url` | Char(2048) | Normalized for dedup |
| `source` | FK → Source | Parent source |
| `promoted_article` | FK → Article | Linked article after promotion |
| `seed_type` | Char(30) | 'article', 'listing', 'feed', 'unknown' |
| `status` | Char(20) | Seed state |

**Phase 16 Scoring Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `relevance_score` | Integer | Topical relevance 0-100 |
| `utility_score` | Integer | Scrape utility 0-100 |
| `freshness_score` | Integer | Activity/freshness 0-100 |
| `authority_score` | Integer | Source authority 0-100 |
| `overall_score` | Integer | Weighted composite 0-100 |

**Phase 16 Provenance Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `query_used` | Char(500) | Discovery query that found this seed |
| `referrer_url` | URL(2000) | Source URL of discovery |
| `discovery_run_id` | UUID | Link to DiscoveryRun |

**Phase 16 Review Workflow Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `review_status` | Char(20) | 'pending', 'reviewed', 'approved', 'rejected' |
| `review_notes` | Text | Notes from review |
| `reviewed_at` | DateTime | Review timestamp |
| `reviewed_by` | FK → User | Reviewer |

**Status State Machine**:

```
    ┌────────────┐
    │  pending   │
    └─────┬──────┘
          │ validate
          ▼
    ┌────────────┐
    │ validating │
    └─────┬──────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌────────┐  ┌────────┐
│  valid │  │invalid │
└────┬───┘  └────────┘
     │ promote
     ▼
┌────────────┐
│  promoted  │
└────────────┘
```

**Phase 16 Review Status State Machine**:

```
    ┌────────────┐
    │  pending   │ ◄── Discovery creates seeds in pending review
    └─────┬──────┘
          │ operator review
          ▼
    ┌────────────┐
    │  reviewed  │
    └─────┬──────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌──────────┐  ┌──────────┐
│ approved │  │ rejected │
└──────────┘  └──────────┘
     │
     │ validate + promote
     ▼
```

**Indexes**:
- `normalized_url` (for dedup lookups)
- `source_id, status` (for source filtering)
- `discovered_at`
- `review_status` (Phase 16)
- `overall_score` (Phase 16)
- `discovery_run_id` (Phase 16)

### 4.2 SeedRawCapture (Phase 16)

**Location**: `apps/seeds/models.py`

Stores raw HTTP response captures for audit and later extraction.

```python
class SeedRawCapture(BaseModel):
    # Size thresholds
    MAX_INLINE_SIZE = 50 * 1024   # 50KB inline
    MAX_CAPTURE_SIZE = 500 * 1024 # 500KB max total
    
    # URL info
    url = models.URLField(max_length=2000)
    final_url = models.URLField(max_length=2000, blank=True)
    
    # HTTP response metadata
    status_code = models.IntegerField(default=0)
    headers = models.JSONField(default=dict, blank=True)
    content_type = models.CharField(max_length=200, blank=True)
    
    # Content storage
    body_hash = models.CharField(max_length=64, db_index=True)
    body_size = models.IntegerField(default=0)
    body_compressed = models.BinaryField(null=True, blank=True)
    body_path = models.CharField(max_length=500, blank=True)
    
    # Fetch metadata
    fetch_mode = models.CharField(max_length=20, choices=FETCH_MODE_CHOICES)
    fetch_timestamp = models.DateTimeField(auto_now_add=True)
    fetch_duration_ms = models.IntegerField(default=0)
    
    # Discovery context
    discovery_run_id = models.UUIDField(null=True, blank=True, db_index=True)
    seed = models.ForeignKey(Seed, null=True, blank=True, on_delete=models.CASCADE)
    
    # Error tracking
    error = models.TextField(blank=True)
```

| Field | Type | Description |
|-------|------|-------------|
| `url` | URL(2000) | Originally requested URL |
| `final_url` | URL(2000) | URL after redirects |
| `status_code` | Integer | HTTP status code |
| `headers` | JSON | Response headers |
| `body_hash` | Char(64) | SHA-256 for dedup |
| `body_size` | Integer | Original body size in bytes |
| `body_compressed` | Binary | Gzipped body if ≤50KB |
| `body_path` | Char(500) | File path if >50KB |
| `fetch_mode` | Char(20) | 'static', 'rendered', 'api' |

**Storage Strategy**:

```
Body Size Decision Tree:
─────────────────────────
body_size ≤ 50KB  →  Store in body_compressed (inline gzip)
body_size > 50KB  →  Store in MEDIA_ROOT/captures/{hash[:2]}/{hash}.gz
body_size > 500KB →  Truncate to 500KB before storage
```

**Key Methods**:

```python
@classmethod
def from_response(cls, url, response, fetch_mode='static', ...):
    """Create capture from requests.Response object."""
    
def get_body(self) -> bytes:
    """Get decompressed body content."""
    
def get_text(self, encoding='utf-8') -> str:
    """Get body as decoded text."""
    
def delete_file(self):
    """Delete associated file if exists."""
```

**Indexes**:
- `body_hash` (for deduplication)
- `discovery_run_id` (for run grouping)
- `fetch_timestamp` (for date filtering)
- `url` (for lookup)

### 4.3 DiscoveryRun (Phase 16)

**Location**: `apps/seeds/models.py`

Tracks a discovery run session, grouping captures and seeds.

```python
class DiscoveryRun(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Target brief
    theme = models.CharField(max_length=200)
    geography = models.JSONField(default=list, blank=True)
    entity_types = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    
    # Execution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    queries_generated = models.IntegerField(default=0)
    urls_discovered = models.IntegerField(default=0)
    captures_created = models.IntegerField(default=0)
    seeds_created = models.IntegerField(default=0)
    
    # Configuration
    config = models.JSONField(default=dict, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    
    # User tracking
    started_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
```

| Field | Type | Description |
|-------|------|-------------|
| `theme` | Char(200) | Discovery theme/topic |
| `geography` | JSON | Target countries/regions list |
| `entity_types` | JSON | Target entity types list |
| `keywords` | JSON | Additional keywords |
| `status` | Char(20) | Run state |
| `queries_generated` | Integer | Count of queries run |
| `urls_discovered` | Integer | Total URLs found |
| `captures_created` | Integer | Captures stored |
| `seeds_created` | Integer | Seeds promoted |

**Status State Machine**:

```
┌─────────┐
│ pending │
└────┬────┘
     │ start
     ▼
┌─────────┐
│ running │
└────┬────┘
     │
     ├───────────┬──────────┐
     ▼           ▼          ▼
┌───────────┐ ┌────────┐ ┌───────────┐
│ completed │ │ failed │ │ cancelled │
└───────────┘ └────────┘ └───────────┘
```

**Computed Properties**:

```python
@property
def duration(self):
    """Calculate run duration."""
    if self.started_at and self.completed_at:
        return self.completed_at - self.started_at
    return None
```

**Indexes**:
- `status`
- `-created_at` (for ordering)

---

## 5. Articles Models

### 5.1 Article

**Location**: `apps/articles/models.py`

```python
class Article(BaseModel):
    # Identity
    url = models.URLField(max_length=2048, unique=True)
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=255, blank=True)
    
    # Relationships
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    
    # Content
    raw_html = models.TextField(blank=True)
    extracted_text = models.TextField(blank=True)
    content_translated = models.TextField(blank=True)
    
    # Metadata
    original_language = models.CharField(max_length=10, blank=True)
    published_date = models.DateTimeField(null=True)
    collected_at = models.DateTimeField(auto_now_add=True)
    word_count = models.IntegerField(default=0)
    images_count = models.IntegerField(default=0)
    
    # Classification
    primary_topic = models.CharField(max_length=100, blank=True)
    primary_region = models.CharField(max_length=100, blank=True)
    secondary_topics = models.JSONField(default=list, blank=True)
    secondary_regions = models.JSONField(default=list, blank=True)
    
    # Quality signals
    has_data_statistics = models.BooleanField(default=False)
    has_citations = models.BooleanField(default=False)
    ai_content_detected = models.BooleanField(default=False)
    
    # Scoring
    total_score = models.IntegerField(default=0)
    quality_category = models.CharField(max_length=20, blank=True)
    
    # Processing
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    processing_error = models.TextField(blank=True)
    
    # Usage tracking
    used_in_content = models.BooleanField(default=False)
    used_in_content_at = models.DateTimeField(null=True)
    
    # Flexible storage
    metadata = models.JSONField(default=dict, blank=True)
```

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `url` | URL(2048) | Unique article URL |
| `processing_status` | Char(20) | Pipeline state |
| `total_score` | Integer | Composite quality score (0-100) |
| `quality_category` | Char(20) | 'high', 'medium', 'low' |
| `content_translated` | Text | English content |
| `primary_topic` | Char(100) | Main topic classification |
| `primary_region` | Char(100) | Main region classification |

**Processing Status State Machine**:

```
┌───────────┐
│ collected │ ← Initial state
└─────┬─────┘
      │ extract
      ▼
┌───────────┐
│extracting │
└─────┬─────┘
      │
      ▼
┌───────────┐
│ extracted │
└─────┬─────┘
      │ translate (if non-English)
      ▼
┌───────────┐
│translating│
└─────┬─────┘
      │
      ▼
┌───────────┐
│translated │
└─────┬─────┘
      │ score
      ▼
┌───────────┐
│  scoring  │
└─────┬─────┘
      │
      ▼
┌───────────┐
│  scored   │
└─────┬─────┘
      │ finalize
      ▼
┌───────────┐
│ completed │
└───────────┘

Any state can transition to:
┌────────┐
│ failed │ ← On error
└────────┘
┌─────────┐
│ skipped │ ← Intentional skip
└─────────┘
```

**Indexes**:
- `url` (unique)
- `source_id`
- `processing_status`
- `total_score`
- `primary_topic`
- `primary_region`
- `published_date`
- `collected_at`

**Computed Property**:

```python
@property
def age_days(self) -> int:
    """Days since published or collected."""
    reference = self.published_date or self.collected_at
    if reference:
        return (timezone.now() - reference).days
    return 0
```

### 5.2 ArticleScoreBreakdown

**Location**: `apps/articles/models.py`

```python
class ArticleScoreBreakdown(BaseModel):
    article = models.OneToOneField(Article, on_delete=models.CASCADE)
    
    relevance_score = models.IntegerField(default=0)
    timeliness_score = models.IntegerField(default=0)
    source_reputation_score = models.IntegerField(default=0)
    content_depth_score = models.IntegerField(default=0)
    uniqueness_score = models.IntegerField(default=0)
    
    scoring_metadata = models.JSONField(default=dict, blank=True)
    scored_at = models.DateTimeField(auto_now=True)
```

### 5.3 ArticleLLMArtifact

**Location**: `apps/articles/models.py`

```python
class ArticleLLMArtifact(BaseModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    artifact_type = models.CharField(max_length=50)  # 'summary', 'classification', etc.
    content = models.TextField()
    model_used = models.CharField(max_length=100)
    tokens_used = models.IntegerField(default=0)
```

### 5.4 ExportJob

**Location**: `apps/articles/models.py`

```python
class ExportJob(BaseModel):
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    params = models.JSONField(default=dict, blank=True)
    
    requested_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.BigIntegerField(default=0)
    row_count = models.IntegerField(default=0)
    
    error_message = models.TextField(blank=True)
```

**Format Choices**: `csv`, `json`, `markdown_zip`

**Status State Machine**:

```
pending → running → completed
                 └→ failed
```

---

## 6. Content Models

### 6.1 ContentOpportunity

**Location**: `apps/content/models.py`

```python
class ContentOpportunity(BaseModel):
    # Identity
    headline = models.CharField(max_length=200)
    angle = models.TextField()
    summary = models.TextField(blank=True)
    
    # Classification
    opportunity_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    primary_topic = models.CharField(max_length=100)
    primary_region = models.CharField(max_length=100, blank=True)
    secondary_topics = models.JSONField(default=list, blank=True)
    secondary_regions = models.JSONField(default=list, blank=True)
    
    # Scoring
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2)
    relevance_score = models.DecimalField(max_digits=3, decimal_places=2)
    timeliness_score = models.DecimalField(max_digits=3, decimal_places=2)
    composite_score = models.DecimalField(max_digits=5, decimal_places=2)
    priority = models.IntegerField(default=5)
    
    # Sources
    source_articles = models.ManyToManyField(Article, blank=True)
    source_article_count = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    detection_method = models.CharField(max_length=30)  # 'llm', 'heuristic', 'gap'
    
    # Lifecycle
    expires_at = models.DateTimeField(null=True)
    batch = models.ForeignKey('OpportunityBatch', null=True, on_delete=models.SET_NULL)
```

**Opportunity Types**:
- `trending` - Hot topic with multiple articles
- `gap` - Underrepresented topic/region
- `follow_up` - Story worth following up
- `deep_dive` - High-value article to expand
- `comparison` - Cross-region/topic comparison
- `explainer` - Complex topic explanation
- `roundup` - Multi-article summary

**Status State Machine**:

```
detected → reviewed → approved → in_progress → completed
                   └→ rejected
         └→ expired (auto)
```

### 6.2 ContentDraft

**Location**: `apps/content/models.py`

```python
class ContentDraft(BaseModel):
    # Identity
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=500, blank=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    
    # Classification
    content_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    voice = models.CharField(max_length=30)
    
    # Sources
    source_articles = models.ManyToManyField(Article, blank=True)
    opportunity = models.ForeignKey(ContentOpportunity, null=True, on_delete=models.SET_NULL)
    template = models.ForeignKey('SynthesisTemplate', null=True, on_delete=models.SET_NULL)
    
    # Quality
    quality_score = models.IntegerField(default=0)
    originality_score = models.IntegerField(default=0)
    word_count = models.IntegerField(default=0)
    
    # Metadata
    key_points = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    estimated_read_time = models.CharField(max_length=20, blank=True)
    
    # Generation
    generation_method = models.CharField(max_length=30)  # 'llm', 'template', 'fallback'
    model_used = models.CharField(max_length=100, blank=True)
    tokens_used = models.IntegerField(default=0)
    generation_time_seconds = models.FloatField(default=0)
    
    # Versioning
    version = models.IntegerField(default=1)
    parent_draft = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
```

**Content Types**:
- `blog_post` - 800 words, structured sections
- `newsletter` - 500 words, highlights + deep dive
- `social_thread` - 280 words, 5-8 posts
- `executive_summary` - 300 words, bullets + actions
- `research_brief` - 1200 words, methodology + findings
- `press_release` - 400 words, standard format
- `analysis` - 1000 words, detailed breakdown
- `commentary` - 600 words, opinion piece

### 6.3 SynthesisTemplate

**Location**: `apps/content/models.py`

```python
class SynthesisTemplate(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    content_type = models.CharField(max_length=30)
    
    system_prompt = models.TextField(blank=True)
    prompt_template = models.TextField()
    
    target_word_count = models.IntegerField(default=800)
    voice = models.CharField(max_length=30, default='professional')
    
    is_active = models.BooleanField(default=True)
```

---

## 7. Database Constraints Summary

### 7.1 Unique Constraints

| Model | Field(s) | Purpose |
|-------|----------|---------|
| Source | `domain` | One source per domain |
| Article | `url` | No duplicate articles |
| Seed | `normalized_url` + `source` | Unique per source |
| SeedRawCapture | `body_hash` (de facto) | Content deduplication |
| SynthesisTemplate | `name` | Unique template names |

### 7.2 Foreign Key Relationships

| From | To | On Delete | Nullable |
|------|-----|-----------|----------|
| CrawlJob → Source | CASCADE | Yes |
| CrawlJob → CrawlJob (parent) | SET_NULL | Yes |
| Seed → Source | CASCADE | No |
| Seed → Article | SET_NULL | Yes |
| Seed → User (reviewed_by) | SET_NULL | Yes |
| SeedRawCapture → Seed | CASCADE | Yes |
| DiscoveryRun → User | SET_NULL | Yes |
| Article → Source | CASCADE | No |
| ContentOpportunity → Article | (M2M) | - |
| ContentDraft → ContentOpportunity | SET_NULL | Yes |
| ContentDraft → Article | (M2M) | - |

### 7.3 Index Summary

| Table | Indexed Fields | Type |
|-------|----------------|------|
| source | `domain` | Unique |
| source | `is_active`, `region` | Composite |
| crawljob | `status`, `started_at` | Composite |
| crawljob | `source_id` | FK |
| seed | `normalized_url` | Index |
| seed | `source_id, status` | Composite |
| seed | `review_status` | Index (Phase 16) |
| seed | `overall_score` | Index (Phase 16) |
| seed | `discovery_run_id` | Index (Phase 16) |
| seedrawcapture | `body_hash` | Index (Phase 16) |
| seedrawcapture | `discovery_run_id` | Index (Phase 16) |
| seedrawcapture | `fetch_timestamp` | Index (Phase 16) |
| discoveryrun | `status` | Index (Phase 16) |
| discoveryrun | `-created_at` | Index (Phase 16) |
| article | `url` | Unique |
| article | `processing_status` | Index |
| article | `total_score` | Index |
| article | `source_id` | FK |
| contentopportunity | `status` | Index |
| contentopportunity | `composite_score` | Index |
| contentdraft | `status` | Index |

---

## 8. Migration History

### 8.1 Sources Migrations

| Migration | Description |
|-----------|-------------|
| `0001_initial` | Source model |
| `0002_crawljob` | CrawlJob model |
| `0003_crawljob_parent` | Multi-source support |
| `0004_source_pagination` | Pagination state field |
| `0005_crawljobsourceresult` | Per-source results |
| `0006_crawljob_indexes` | Date filter optimization |

### 8.2 Articles Migrations

| Migration | Description |
|-----------|-------------|
| `0001_initial` | Article base model |
| `0002_article_scoring` | Score fields |
| `0003_articlelllmartifact` | LLM artifacts |
| `0004_exportjob` | Export functionality |
| `0005_article_classification` | Topic/region fields |

### 8.3 Content Migrations

| Migration | Description |
|-----------|-------------|
| `0001_initial` | ContentOpportunity, ContentDraft |
| `0002_opportunitybatch` | Batch processing |
| `0003_synthesistemplate` | Custom templates |
| `0004_draftfeedback` | User feedback |

### 8.4 Seeds Migrations (Phase 16)

| Migration | Description |
|-----------|-------------|
| `0001_initial` | Seed, SeedBatch models |
| `0002_seed_discovery` | Phase 16: Discovery provenance fields |
| `0003_seed_scoring` | Phase 16: Multi-dimensional scoring fields |
| `0004_seed_review` | Phase 16: Review workflow fields |
| `0005_seedrawcapture` | Phase 16: SeedRawCapture model |
| `0006_discoveryrun` | Phase 16: DiscoveryRun model |

---

**Document Version**: 2.0.0  
**Last Updated**: Session 30 (Phase 16)  
**Maintainer**: EMCIP Development Team
