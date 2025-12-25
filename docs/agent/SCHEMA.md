# Operator Console MVP - Schema Reference

## Existing Models

### BaseModel (Abstract)
```python
# apps/core/models.py
class BaseModel(models.Model):
    id = UUIDField(primary_key=True, default=uuid4)
    created_at = DateTimeField(default=timezone.now)
    updated_at = DateTimeField(auto_now=True)
```

### Source
```python
# apps/sources/models.py
class Source(BaseModel):
    # Identity
    name = CharField(max_length=255)
    domain = CharField(max_length=255, unique=True)
    url = URLField()
    source_type = CharField(choices=SOURCE_TYPE_CHOICES)  # news_site, blog, etc.
    
    # Geographic & Topics
    primary_region = CharField(max_length=100)
    primary_topics = JSONField(default=list)
    languages = JSONField(default=list)
    
    # Quality
    quality_indicators = JSONField(default=list)
    reputation_score = IntegerField(default=50, validators=[0-100])
    
    # Crawl Config
    crawl_frequency_hours = IntegerField(default=24)
    crawler_type = CharField(choices=[http, scrapy, playwright])
    crawler_config = JSONField(default=dict)  # selectors, patterns
    pagination_state = JSONField(default=dict)  # Phase 3 addition
    
    # Status
    status = CharField(choices=[active, paused, inactive, error])
    discovery_method = CharField(choices=[manual, search, referral])
    
    # Statistics
    total_articles_collected = IntegerField(default=0)
    total_articles_used = IntegerField(default=0)
    last_crawled_at = DateTimeField(null=True)
    crawl_errors_count = IntegerField(default=0)
    
    # Technical
    requires_javascript = BooleanField(default=False)
    robots_txt_compliant = BooleanField(default=True)
    custom_headers = JSONField(default=dict)
```

### CrawlJob
```python
# apps/sources/models.py
class CrawlJob(BaseModel):
    source = ForeignKey(Source, related_name='crawl_jobs')
    status = CharField(choices=[pending, running, completed, failed])
    started_at = DateTimeField(null=True)
    completed_at = DateTimeField(null=True)
    
    # Results
    total_found = IntegerField(default=0)
    new_articles = IntegerField(default=0)
    duplicates = IntegerField(default=0)
    errors = IntegerField(default=0)
    pages_crawled = IntegerField(default=0)
    error_message = TextField(blank=True)
    
    # Celery
    task_id = CharField(max_length=255, blank=True)
```

### Article
```python
# apps/articles/models.py
class Article(BaseModel):
    source = ForeignKey(Source, related_name='articles')
    url = URLField()
    
    # Content
    title = CharField(max_length=500)
    author = CharField(max_length=255, blank=True)
    published_date = DateTimeField(null=True)
    collected_at = DateTimeField(default=timezone.now)
    raw_html = TextField(blank=True)
    extracted_text = TextField(blank=True)
    original_language = CharField(max_length=10, blank=True)
    translated_text = TextField(blank=True)
    word_count = IntegerField(default=0)
    
    # Content Flags
    has_data_statistics = BooleanField(default=False)
    has_citations = BooleanField(default=False)
    images_count = IntegerField(default=0)
    
    # Categorization
    primary_region = CharField(choices=REGION_CHOICES)
    secondary_regions = JSONField(default=list)
    primary_topic = CharField(max_length=100)
    topics = JSONField(default=list)
    
    # Scoring (0-100)
    reputation_score = IntegerField(default=0)
    recency_score = IntegerField(default=0)
    topic_alignment_score = IntegerField(default=0)
    content_quality_score = IntegerField(default=0)
    geographic_relevance_score = IntegerField(default=0)
    ai_penalty = IntegerField(default=0)
    total_score = IntegerField(default=0)
    
    # AI Detection
    ai_content_detected = BooleanField(default=False)
    ai_confidence_score = FloatField(default=0.0)
    ai_detection_reasoning = TextField(blank=True)
    
    # Processing
    processing_status = CharField(choices=PROCESSING_STATUS_CHOICES)
    processing_error = TextField(blank=True)
    
    # Usage
    used_in_content = BooleanField(default=False)
    usage_count = IntegerField(default=0)
    metadata = JSONField(default=dict)
```

---

## New Models (Phase 10.1+)

### OperatorProfile (Phase 10.1)
```python
# apps/core/models.py (or apps/auth/models.py)
class OperatorProfile(BaseModel):
    user = OneToOneField(User, on_delete=CASCADE, related_name='operator_profile')
    
    # Role & Permissions
    role = CharField(choices=[admin, operator, viewer], default='operator')
    
    # Preferences
    preferences = JSONField(default=dict)  # UI prefs, defaults
    timezone = CharField(max_length=50, default='UTC')
    
    # Session
    last_active_at = DateTimeField(null=True)
    
    class Meta:
        db_table = 'operator_profiles'
```

### Extended CrawlJob Fields (Phase 10.2)
```python
# apps/sources/models.py - additions to CrawlJob
class CrawlJob(BaseModel):
    # ... existing fields ...
    
    # NEW: Run configuration
    config_overrides = JSONField(default=dict)  # max_pages, timeout, etc.
    priority = IntegerField(default=5)  # 1-10, higher = more urgent
    triggered_by = CharField(choices=[schedule, manual, api], default='manual')
    schedule = ForeignKey('django_celery_beat.PeriodicTask', null=True, on_delete=SET_NULL)
    
    # NEW: Multi-source support
    is_multi_source = BooleanField(default=False)
```

### CrawlJobSourceResult (Phase 10.2)
```python
# apps/sources/models.py
class CrawlJobSourceResult(BaseModel):
    """Per-source results for multi-source CrawlJobs"""
    crawl_job = ForeignKey(CrawlJob, related_name='source_results')
    source = ForeignKey(Source, related_name='crawl_results')
    
    status = CharField(choices=[pending, running, completed, failed])
    started_at = DateTimeField(null=True)
    completed_at = DateTimeField(null=True)
    
    articles_found = IntegerField(default=0)
    articles_new = IntegerField(default=0)
    articles_duplicate = IntegerField(default=0)
    errors_count = IntegerField(default=0)
    error_message = TextField(blank=True)
    
    class Meta:
        db_table = 'crawl_job_source_results'
        unique_together = ['crawl_job', 'source']
```

### Seed (Phase 10.4)
```python
# apps/seeds/models.py
class Seed(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending Validation'),
        ('validating', 'Validating'),
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('promoted', 'Promoted to Source'),
        ('rejected', 'Rejected'),
    ]
    
    url = URLField(unique=True)
    domain = CharField(max_length=255, db_index=True)  # extracted from URL
    
    # Validation
    status = CharField(choices=STATUS_CHOICES, default='pending')
    validation_result = JSONField(default=dict)  # errors, warnings, info
    validated_at = DateTimeField(null=True)
    
    # Discovery
    discovered_by = ForeignKey(User, null=True, on_delete=SET_NULL)
    discovered_at = DateTimeField(default=timezone.now)
    discovery_source = CharField(max_length=100, blank=True)  # 'import', 'manual', 'crawler'
    
    # Promotion
    promoted_at = DateTimeField(null=True)
    promoted_to_source = ForeignKey('sources.Source', null=True, on_delete=SET_NULL)
    
    # Metadata
    notes = TextField(blank=True)
    suggested_name = CharField(max_length=255, blank=True)
    suggested_type = CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'seeds'
        ordering = ['-discovered_at']
```

### ArticleRawCapture (Phase 10.5)
```python
# apps/articles/models.py
class ArticleRawCapture(BaseModel):
    article = OneToOneField(Article, on_delete=CASCADE, related_name='raw_capture')
    
    raw_html = TextField()
    response_headers = JSONField(default=dict)
    http_status = IntegerField()
    content_type = CharField(max_length=100, blank=True)
    encoding = CharField(max_length=50, blank=True)
    
    fetched_at = DateTimeField(default=timezone.now)
    fetch_duration_ms = IntegerField(default=0)
    fetcher_type = CharField(max_length=50)  # http, playwright, hybrid
    
    class Meta:
        db_table = 'article_raw_captures'
```

### ArticleScoring (Phase 10.5)
```python
# apps/articles/models.py
class ArticleScoring(BaseModel):
    article = ForeignKey(Article, on_delete=CASCADE, related_name='scoring_history')
    
    # Score Components (raw values)
    reputation_raw = FloatField(default=0)
    recency_raw = FloatField(default=0)
    topic_alignment_raw = FloatField(default=0)
    content_quality_raw = FloatField(default=0)
    geographic_relevance_raw = FloatField(default=0)
    ai_penalty_raw = FloatField(default=0)
    
    # Normalized scores (0-100)
    reputation_score = IntegerField(default=0)
    recency_score = IntegerField(default=0)
    topic_alignment_score = IntegerField(default=0)
    content_quality_score = IntegerField(default=0)
    geographic_relevance_score = IntegerField(default=0)
    ai_penalty = IntegerField(default=0)
    total_score = IntegerField(default=0)
    
    # Metadata
    scoring_version = CharField(max_length=20, default='1.0')
    scoring_config = JSONField(default=dict)  # weights used
    scored_at = DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'article_scorings'
        ordering = ['-scored_at']
```

### ArticleLLMArtifact (Phase 10.5)
```python
# apps/articles/models.py
class ArticleLLMArtifact(BaseModel):
    article = ForeignKey(Article, on_delete=CASCADE, related_name='llm_artifacts')
    
    artifact_type = CharField(max_length=50)  # ai_detection, summary, topic_extraction
    prompt_name = CharField(max_length=100)
    prompt_version = CharField(max_length=20)
    
    prompt_text = TextField()
    system_prompt = TextField(blank=True)
    response_text = TextField()
    parsed_result = JSONField(default=dict)
    
    # Cost tracking
    model = CharField(max_length=100)
    input_tokens = IntegerField(default=0)
    output_tokens = IntegerField(default=0)
    cost_usd = FloatField(default=0.0)
    
    # Metadata
    duration_ms = IntegerField(default=0)
    cached = BooleanField(default=False)
    
    class Meta:
        db_table = 'article_llm_artifacts'
        ordering = ['-created_at']
```

### ArticleImage (Phase 10.5)
```python
# apps/articles/models.py
class ArticleImage(BaseModel):
    article = ForeignKey(Article, on_delete=CASCADE, related_name='images')
    
    url = URLField()
    alt_text = CharField(max_length=500, blank=True)
    caption = TextField(blank=True)
    
    # Analysis
    width = IntegerField(null=True)
    height = IntegerField(null=True)
    file_size_bytes = IntegerField(null=True)
    mime_type = CharField(max_length=50, blank=True)
    
    # Relevance
    is_primary = BooleanField(default=False)  # Main article image
    position = IntegerField(default=0)  # Order in article
    
    class Meta:
        db_table = 'article_images'
        ordering = ['position']
```

### LLMSettings (Phase 10.6)
```python
# apps/content/models.py
class LLMSettings(BaseModel):
    """Singleton model for LLM configuration"""
    
    # Model Settings
    default_model = CharField(max_length=100, default='claude-sonnet-4-20250514')
    fallback_model = CharField(max_length=100, blank=True)
    temperature = FloatField(default=0.7)
    max_tokens = IntegerField(default=4000)
    
    # Budget
    daily_budget_usd = FloatField(default=10.0)
    monthly_budget_usd = FloatField(default=300.0)
    budget_alert_threshold = FloatField(default=0.8)  # 80% of budget
    
    # Feature Toggles
    ai_detection_enabled = BooleanField(default=True)
    translation_enabled = BooleanField(default=True)
    content_synthesis_enabled = BooleanField(default=True)
    caching_enabled = BooleanField(default=True)
    
    # Rate Limiting
    requests_per_minute = IntegerField(default=60)
    concurrent_requests = IntegerField(default=5)
    
    class Meta:
        db_table = 'llm_settings'
        verbose_name = 'LLM Settings'
        verbose_name_plural = 'LLM Settings'
    
    @classmethod
    def get_settings(cls):
        """Get or create singleton settings instance"""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

---

## Relationships Diagram

```
User ─────1:1───── OperatorProfile

Source ────1:N───── CrawlJob ────1:N───── CrawlJobSourceResult
   │                    │
   │                    └── schedule ──► PeriodicTask (django-celery-beat)
   │
   └────1:N───── Article ────1:1───── ArticleRawCapture
                    │
                    ├────1:N───── ArticleScoring
                    ├────1:N───── ArticleLLMArtifact
                    └────1:N───── ArticleImage

Seed ────────────────► (promoted_to) ──► Source
```

---

## Indexes to Add

```python
# High-priority indexes for console queries
CrawlJob:
  - (status, created_at)  # Filter by status, sort by date
  - (source_id, status)   # Source run history

Article:
  - (source_id, processing_status)  # Source article list
  - (total_score, processing_status)  # Top articles
  
Seed:
  - (status, discovered_at)  # Seed queue
  - (domain)  # Duplicate check
```
