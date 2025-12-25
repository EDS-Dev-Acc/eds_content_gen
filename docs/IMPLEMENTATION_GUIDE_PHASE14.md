# Phase 14: Implementation Guide

**Version**: 1.0  
**Created**: December 2025  
**Status**: Ready for Implementation

---

## Overview

This guide breaks down the Phase 14 improvements into three manageable implementation parts:

| Part | Focus Area | Estimated Effort | Dependencies |
|------|------------|------------------|--------------|
| **Part 1** | Seeds Enhancements | 1-2 sessions | None |
| **Part 2** | Sources/Runs/Orchestration | 1-2 sessions | Part 1 (partial) |
| **Part 3** | Articles Export & Observability | 1-2 sessions | Part 2 (partial) |

---

# Part 1: Seeds Enhancements

## 1A. Import Normalization and on_duplicate

### Objective
- Normalize all incoming URLs using `URLNormalizer`
- Deduplicate by `normalized_url`, not raw `url`
- Support `on_duplicate` modes: `skip` | `update` | `error`
- Return detailed duplicate metadata with merge diffs

### API Contract

**Request**: `POST /api/seeds/import/`
```json
{
  "format": "urls|text|csv",
  "urls": ["https://example.com/page", "..."],
  "tags": ["sea", "tier1"],
  "on_duplicate": "skip|update|error",
  "update_fields": ["tags", "notes", "confidence", "seed_type", "country", "regions", "topics"]
}
```

**Response** (enhanced):
```json
{
  "batch_id": "uuid",
  "total": 42,
  "created": 30,
  "duplicates": 10,
  "updated": 2,
  "errors": 0,
  "created_seeds": [...],
  "updated_seeds": [...],
  "duplicates_detail": [
    {
      "url": "https://Example.COM/page/",
      "normalized_url": "https://example.com/page",
      "existing_id": "uuid",
      "action": "skipped|updated|error",
      "merged_fields": {
        "tags": { "before": ["a"], "after": ["a", "sea"] }
      }
    }
  ],
  "error_details": [...]
}
```

### Files to Modify

#### 1. `apps/seeds/serializers.py`

**Add to `SeedBulkImportSerializer`**:
```python
on_duplicate = serializers.ChoiceField(
    choices=['skip', 'update', 'error'],
    default='skip',
    help_text="Strategy for duplicates: skip (ignore), update (merge), error (report)"
)

update_fields = serializers.ListField(
    child=serializers.CharField(),
    required=False,
    default=list,
    help_text="Fields to update on duplicate (for update mode)"
)

ALLOWED_UPDATE_FIELDS = ['tags', 'notes', 'confidence', 'seed_type', 'country', 'regions', 'topics']

def validate_update_fields(self, value):
    """Validate update_fields against allowlist."""
    invalid = [f for f in value if f not in self.ALLOWED_UPDATE_FIELDS]
    if invalid:
        raise serializers.ValidationError(
            f"Invalid update fields: {invalid}. Allowed: {self.ALLOWED_UPDATE_FIELDS}"
        )
    return value
```

#### 2. `apps/seeds/views.py::SeedBulkImportView`

**Replace import logic with**:
```python
def post(self, request):
    from apps.core.security import URLNormalizer
    
    serializer = SeedBulkImportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    urls = serializer.extract_urls(data)
    tags = data.get('tags', [])
    on_duplicate = data.get('on_duplicate', 'skip')
    update_fields = data.get('update_fields', [])
    
    # Create batch record
    batch = SeedBatch.objects.create(...)
    
    created = []
    updated = []
    duplicates_detail = []
    errors = []
    
    with transaction.atomic():
        for url in urls:
            # Normalize URL
            try:
                normalized = URLNormalizer.normalize(url)
            except Exception:
                normalized = url
            
            # Check for duplicate by normalized_url
            existing = Seed.objects.filter(
                normalized_url=normalized
            ).exclude(status='promoted').first()
            
            if existing:
                if on_duplicate == 'skip':
                    duplicates_detail.append({
                        'url': url,
                        'normalized_url': normalized,
                        'existing_id': str(existing.id),
                        'action': 'skipped',
                    })
                elif on_duplicate == 'update':
                    # Merge fields
                    merged_fields = {}
                    
                    if 'tags' in update_fields or not update_fields:
                        before_tags = list(existing.tags or [])
                        existing.tags = list(dict.fromkeys(before_tags + tags))
                        if existing.tags != before_tags:
                            merged_fields['tags'] = {
                                'before': before_tags,
                                'after': existing.tags
                            }
                    
                    if 'notes' in update_fields and data.get('notes'):
                        before_notes = existing.notes or ''
                        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                        existing.notes = f"{before_notes}\n[Import merge {timestamp}]: {data['notes']}".strip()
                        merged_fields['notes'] = {'before': before_notes, 'after': existing.notes}
                    
                    # Other fields...
                    existing.import_batch_id = batch.id
                    existing.save()
                    
                    updated.append({
                        'id': str(existing.id),
                        'url': existing.url,
                        'domain': existing.domain,
                        'merged_fields': merged_fields,
                    })
                else:  # error
                    duplicates_detail.append({
                        'url': url,
                        'normalized_url': normalized,
                        'existing_id': str(existing.id),
                        'action': 'error',
                    })
                    errors.append({'url': url, 'error': 'Duplicate URL'})
                continue
            
            # Create new seed
            seed = Seed.objects.create(
                url=url,
                tags=tags,
                import_source=data.get('format', 'api'),
                import_batch_id=batch.id,
                added_by=request.user,
            )
            created.append({...})
    
    # Update batch stats
    batch.success_count = len(created) + len(updated)
    batch.duplicate_count = len([d for d in duplicates_detail if d['action'] == 'skipped'])
    batch.error_count = len(errors)
    batch.save()
    
    return Response({
        'batch_id': str(batch.id),
        'total': len(urls),
        'created': len(created),
        'updated': len(updated),
        'duplicates': len(duplicates_detail),
        'errors': len(errors),
        'created_seeds': created[:10],
        'updated_seeds': updated[:10],
        'duplicates_detail': duplicates_detail[:20],
        'error_details': errors[:10],
    }, status=status.HTTP_201_CREATED)
```

### Merge Rules (Reference)

| Field | Merge Behavior |
|-------|----------------|
| `tags` | Union unique, preserve order (existing first, then new) |
| `notes` | Append with delimiter `\n[Import merge YYYY-MM-DD]: ` |
| `seed_type` | Update only if provided and in `update_fields` |
| `country` | Update only if provided and in `update_fields` |
| `regions` | Update only if provided and in `update_fields` |
| `topics` | Update only if provided and in `update_fields` |
| `confidence` | Update only if provided and in `update_fields` |

**Never overwrite**: Promoted seeds (status='promoted')

### Acceptance Criteria

- [ ] `on_duplicate=skip`: Duplicates counted but not modified
- [ ] `on_duplicate=update`: Tags merged, notes appended, `updated` count returned
- [ ] `on_duplicate=error`: Duplicates added to `error_details`
- [ ] Deduplication uses `normalized_url` (catches URL variants)
- [ ] `duplicates_detail` includes `merged_fields` for updates
- [ ] Promoted seeds never modified
- [ ] Batch stats reflect all outcomes

### Test Cases

```python
def test_import_skip_mode():
    """Duplicates are skipped silently."""
    # Create existing seed
    # Import same URL with on_duplicate=skip
    # Assert: duplicates=1, created=0, duplicates_detail[0].action='skipped'

def test_import_update_mode_tags_merge():
    """Tags are merged with existing."""
    # Create seed with tags=['a']
    # Import same URL with tags=['b'], on_duplicate=update
    # Assert: seed.tags=['a','b'], updated=1
    # Assert: merged_fields.tags.before=['a'], after=['a','b']

def test_import_error_mode():
    """Duplicates reported as errors."""
    # Import same URL with on_duplicate=error
    # Assert: errors=1, error_details contains 'Duplicate URL'

def test_normalized_url_catches_variants():
    """URLs normalized before dedup."""
    # Create seed for 'https://example.com/page'
    # Import 'https://EXAMPLE.COM/page/' (trailing slash, caps)
    # Assert: treated as duplicate
```

---

## 1B. Validate Robots Warnings

### Objective
- Return `warnings[]` array when robots.txt fails
- Include `final_url`, `content_type`, `detected` hints
- Don't silently assume crawlable

### API Contract (Enhanced Response)

```json
{
  "id": "uuid",
  "status": "valid|invalid",
  "is_reachable": true,
  "is_crawlable": true,
  "has_articles": true,
  "article_count_estimate": 25,
  "errors": [],
  "warnings": [
    "robots.txt fetch failed; assuming crawlable",
    "URL redirected from http to https"
  ],
  "final_url": "https://www.example.com/",
  "content_type": "text/html",
  "detected": {
    "type_hint": "news|blog|rss|sitemap|unknown",
    "feed_urls": ["https://example.com/feed"],
    "sitemap_url": "https://example.com/sitemap.xml"
  },
  "is_promotable": true,
  "message": "Seed validation complete: valid"
}
```

### Files to Modify

#### `apps/seeds/views.py::SeedValidateView`

**Current state**: Already enhanced in Session 23 with `warnings`, `final_url`, `content_type`, `detected`. 

**Verify/Add**:
1. Robots.txt failure adds warning (not error)
2. `final_url` captured from `response.url`
3. `content_type` captured from headers
4. `detected.type_hint` infers content type

**Robots warning logic**:
```python
# In robots.txt handling section
try:
    robots_response = client.get(robots_url, validate_content_type=False)
    rp.parse(robots_response.text.splitlines())
    is_crawlable = rp.can_fetch('*', seed.url)
except Exception as e:
    # Add warning instead of silently assuming crawlable
    warnings.append(f"robots.txt fetch failed ({str(e)[:50]}); assuming crawlable")
    is_crawlable = True

if not is_crawlable:
    warnings.append("robots.txt restricts crawling for this URL")
```

### Acceptance Criteria

- [ ] `warnings[]` returned in response (empty if none)
- [ ] Robots fetch failure adds warning, sets `is_crawlable=True`
- [ ] `final_url` reflects actual response URL after redirects
- [ ] `content_type` captured from response headers
- [ ] Redirect adds warning ("URL redirected to: X")

### Test Cases

```python
def test_validate_robots_failure_warning():
    """Robots.txt failure returns warning, not error."""
    # Mock SafeHTTPClient.get to raise for robots.txt URL
    # Validate seed
    # Assert: warnings contains 'robots.txt fetch failed'
    # Assert: is_crawlable=True, status='valid' (if reachable)

def test_validate_redirect_warning():
    """Redirects captured in final_url and warnings."""
    # Mock response.url different from request URL
    # Assert: final_url=response.url
    # Assert: warnings contains 'URL redirects to'
```

---

## 1C. Test-Crawl Parameters

### Objective
- Accept `entrypoint_url` parameter (same-origin only)
- Enforce `max_pages` (cap 20), `max_articles` (cap 10)
- Return `entrypoint_url` in response

### API Contract

**Request**: `POST /api/seeds/{id}/test-crawl/`
```json
{
  "entrypoint_url": "https://example.com/news/",
  "max_pages": 15,
  "max_articles": 8,
  "follow_links": true
}
```

**Response** (enhanced):
```json
{
  "seed_id": "uuid",
  "seed_url": "https://example.com/",
  "entrypoint_url": "https://example.com/news/",
  "sample_articles": [...],
  "stats": {
    "pages_fetched": 10,
    "max_pages": 15,
    "links_found": 70,
    "articles_detected": 6,
    "errors": []
  },
  "success": true,
  "message": "Test crawl complete"
}
```

### Files to Modify

#### `apps/seeds/views.py::SeedTestCrawlView`

**Current state**: Already enhanced in Session 23 with `entrypoint_url`, `max_pages`, `max_articles`.

**Verify**:
1. `entrypoint_url` validated as same-origin
2. Server caps enforced: `max_pages ≤ 20`, `max_articles ≤ 10`
3. `entrypoint_url` returned in response
4. Discovered links normalized before dedup

### Acceptance Criteria

- [ ] `entrypoint_url` accepted and validated (same domain)
- [ ] Foreign domain returns 400 with VALIDATION_ERROR
- [ ] `max_pages` capped at 20, `max_articles` capped at 10
- [ ] Response includes actual `entrypoint_url` used
- [ ] Stats reflect enforced caps

### Test Cases

```python
def test_testcrawl_entrypoint_same_origin():
    """Entrypoint on same domain accepted."""
    # Seed for example.com
    # Request entrypoint_url=example.com/news/
    # Assert: response.entrypoint_url matches request

def test_testcrawl_entrypoint_foreign_rejected():
    """Entrypoint on different domain rejected."""
    # Seed for example.com
    # Request entrypoint_url=other.com/news/
    # Assert: 400 with validation error

def test_testcrawl_caps_enforced():
    """Server caps override client requests."""
    # Request max_pages=50, max_articles=20
    # Assert: stats.max_pages=20, actual fetch ≤ 20
```

---

# Part 2: Sources/Runs/Orchestration

## 2A. Sources CRUD/Test/Crawl-Now

### Objective
- Ensure full CRUD for Sources
- Add `test` action (SSRF-safe connectivity check)
- Add `crawl-now` action (trigger single-source run)

### Endpoints

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/sources/` | List with filters |
| POST | `/api/sources/` | Create source |
| GET | `/api/sources/{id}/` | Detail |
| PATCH | `/api/sources/{id}/` | Partial update |
| DELETE | `/api/sources/{id}/` | Delete (admin only) |
| POST | `/api/sources/{id}/test/` | Test connectivity |
| POST | `/api/sources/{id}/crawl-now/` | Trigger crawl run |
| GET | `/api/sources/stats/` | Aggregate statistics |

### Files to Modify

#### `apps/sources/views.py`

**Add/Verify SourceViewSet**:
```python
class SourceViewSet(viewsets.ModelViewSet):
    """Full CRUD for Sources with test and crawl-now actions."""
    
    permission_classes = [IsAuthenticated]
    queryset = Source.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SourceCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return SourceUpdateSerializer
        elif self.action == 'retrieve':
            return SourceDetailSerializer
        return SourceListSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Add filters: status, type, region, tags
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        # ... more filters
        return queryset
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test source connectivity with SSRF protection."""
        from apps.core.security import SafeHTTPClient
        
        source = self.get_object()
        client = SafeHTTPClient(timeout=(5, 15))
        
        try:
            start = time.time()
            response = client.head(source.url)
            latency_ms = (time.time() - start) * 1000
            
            return Response({
                'source_id': str(source.id),
                'url': source.url,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type'),
                'latency_ms': round(latency_ms, 2),
                'reachable': response.status_code < 400,
                'warnings': [],  # Add robots warnings if needed
            })
        except Exception as e:
            return Response({
                'source_id': str(source.id),
                'url': source.url,
                'reachable': False,
                'error': str(e),
            }, status=status.HTTP_200_OK)  # Still 200, just reporting
        finally:
            client.close()
    
    @action(detail=True, methods=['post'], url_path='crawl-now')
    def crawl_now(self, request, pk=None):
        """Trigger immediate crawl for this source."""
        source = self.get_object()
        
        # Create CrawlJob
        crawl_job = CrawlJob.objects.create(
            source=source,
            status='pending',
            triggered_by='api',
            triggered_by_user=request.user,
            is_multi_source=False,
        )
        
        # Enqueue task
        try:
            from .tasks import crawl_source
            task = crawl_source.delay(str(source.id), crawl_job_id=str(crawl_job.id))
            crawl_job.task_id = task.id
            crawl_job.status = 'running'
            crawl_job.started_at = timezone.now()
            crawl_job.save()
        except Exception as e:
            crawl_job.status = 'pending'
            crawl_job.error_message = str(e)
            crawl_job.save()
        
        return Response({
            'run_id': str(crawl_job.id),
            'task_id': crawl_job.task_id,
            'source_id': str(source.id),
            'status': crawl_job.status,
        }, status=status.HTTP_201_CREATED)
```

### Acceptance Criteria

- [ ] CRUD operations work with proper permissions
- [ ] `test` endpoint uses SafeHTTPClient (SSRF protection)
- [ ] `test` returns latency, status, content_type
- [ ] `crawl-now` creates CrawlJob and enqueues task
- [ ] `crawl-now` returns run_id and task_id
- [ ] DELETE requires admin permission

### Test Cases

```python
def test_source_crud():
    """Full CRUD lifecycle."""
    # POST create -> 201
    # GET detail -> matches
    # PATCH update -> updated
    # DELETE -> 204 (if admin)

def test_source_test_endpoint():
    """Test endpoint returns connectivity info."""
    # Mock SafeHTTPClient response
    # Assert: latency_ms, status_code, content_type returned

def test_source_crawl_now():
    """Crawl-now creates run and returns IDs."""
    # POST crawl-now
    # Assert: 201, run_id present
    # Assert: CrawlJob created with source
```

---

## 2B. Runs Alias and Filters

### Objective
- Support `POST /api/runs/` as alias
- Add date range filters
- Include `totals` in list response

### API Contract

**POST /api/runs/** (alias for POST /api/runs/start/)
```json
{
  "source_ids": ["uuid1", "uuid2"],
  "priority": 5,
  "config_overrides": {}
}
```

**GET /api/runs/?started_after=2025-01-01&status=completed**
```json
{
  "count": 50,
  "results": [...],
  "totals": {
    "total_runs": 50,
    "total_articles": 1250,
    "new_articles": 980,
    "duplicates": 200,
    "errors": 70,
    "pages_crawled": 5000,
    "avg_duration_seconds": 125.5,
    "by_status": {"completed": 45, "failed": 5}
  }
}
```

### Files to Modify

#### `apps/sources/urls.py`

**Verify POST /api/runs/ works**:
```python
urlpatterns = [
    # Existing
    path('runs/', RunViewSet.as_view({'get': 'list', 'post': 'create'}), name='runs-list'),
    # ...
]
```

#### `apps/sources/views.py::RunViewSet`

**Already implemented in Session 23**: `list()` with totals aggregation.

**Verify filters**:
- `started_after`, `started_before`
- `completed_after`, `completed_before`
- `status`, `source`, `triggered_by`

### Acceptance Criteria

- [ ] `POST /api/runs/` creates run (alias for /runs/start/)
- [ ] Date filters work: `started_after`, `completed_before`, etc.
- [ ] `totals` object included in list response
- [ ] `totals.by_status` shows counts per status

---

## 2C. Orchestration Lifecycle

### Objective
- Worker updates per-source results and parent aggregation
- Honor cancellation mid-crawl

### Behavior Specification

```
crawl_source(source_id, crawl_job_id, config_overrides):
  1. Mark CrawlJobSourceResult.status = 'running', started_at = now()
  2. Check parent CrawlJob.status - if 'cancelled', mark 'skipped' and exit
  3. Execute crawl:
     - Periodically update pages/articles/errors counts
     - Check cancellation between batches
  4. On completion:
     - Set source_result.status = 'completed' or 'failed'
     - Set source_result.completed_at
  5. Aggregate parent CrawlJob:
     - Sum all source_results
     - Set parent.status based on children:
       - All completed → parent completed
       - Any failed AND none running/pending → parent failed
       - Any running/pending → parent still running
```

### Files to Modify

#### `apps/sources/tasks.py`

**Enhance `crawl_source` task**:
```python
@shared_task(bind=True)
def crawl_source(self, source_id, crawl_job_id=None, parent_job_id=None, config_overrides=None):
    """Crawl a source with lifecycle management."""
    
    source = Source.objects.get(id=source_id)
    job_id = crawl_job_id or parent_job_id
    
    # Get or create source result
    if parent_job_id:
        source_result = CrawlJobSourceResult.objects.get(
            crawl_job_id=parent_job_id, source=source
        )
    else:
        source_result = None
    
    # Update to running
    if source_result:
        source_result.status = 'running'
        source_result.started_at = timezone.now()
        source_result.save()
    
    # Check cancellation
    parent_job = CrawlJob.objects.get(id=job_id)
    if parent_job.status == 'cancelled':
        if source_result:
            source_result.status = 'skipped'
            source_result.error_message = 'Parent job cancelled'
            source_result.save()
        return {'status': 'skipped'}
    
    try:
        # Execute crawl...
        # Periodically check: parent_job.refresh_from_db(); if cancelled, abort
        
        # On success
        if source_result:
            source_result.status = 'completed'
            source_result.completed_at = timezone.now()
            source_result.total_found = articles_found
            source_result.new_articles = new_count
            source_result.pages_crawled = pages
            source_result.save()
        
    except Exception as e:
        if source_result:
            source_result.status = 'failed'
            source_result.error_message = str(e)
            source_result.completed_at = timezone.now()
            source_result.save()
        raise
    
    finally:
        # Aggregate parent
        finalize_parent_job(job_id)
    
    return {...}


def finalize_parent_job(crawl_job_id):
    """Recompute parent aggregates atomically."""
    with transaction.atomic():
        job = CrawlJob.objects.select_for_update().get(id=crawl_job_id)
        results = job.source_results.all()
        
        # Aggregate totals
        job.total_found = sum(r.total_found or 0 for r in results)
        job.new_articles = sum(r.new_articles or 0 for r in results)
        job.duplicates = sum(r.duplicates or 0 for r in results)
        job.errors = sum(r.errors or 0 for r in results)
        job.pages_crawled = sum(r.pages_crawled or 0 for r in results)
        
        # Determine status
        statuses = [r.status for r in results]
        if 'running' in statuses or 'pending' in statuses:
            job.status = 'running'
        elif 'failed' in statuses:
            job.status = 'failed'
        elif all(s == 'completed' for s in statuses):
            job.status = 'completed'
            job.completed_at = timezone.now()
        
        job.save()
```

### Acceptance Criteria

- [ ] Source result updated to 'running' at start
- [ ] Cancellation checked before and during crawl
- [ ] Cancelled parent → source marked 'skipped'
- [ ] Source result status set on completion/failure
- [ ] Parent aggregates computed from children
- [ ] Parent status derived from child statuses

### Test Cases

```python
def test_orchestration_all_success():
    """All children complete → parent completed."""
    # Create parent job with 2 sources
    # Run both successfully
    # Assert: parent.status='completed', totals summed

def test_orchestration_one_failure():
    """One child fails → parent failed."""
    # Create parent job with 2 sources
    # One succeeds, one fails
    # Assert: parent.status='failed'

def test_orchestration_cancellation():
    """Cancelled parent → children skip."""
    # Create parent job, set status='cancelled'
    # Run child task
    # Assert: source_result.status='skipped'
```

---

# Part 3: Articles Export & Observability

## 3A. Export Jobs Model and Endpoints

### Objective
- Async export for large datasets
- Track export status and provide download URL

### Model

#### `apps/articles/models.py`

```python
class ExportJob(BaseModel):
    """Track async export jobs."""
    
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    class Format(models.TextChoices):
        CSV = 'csv', 'CSV'
        JSON = 'json', 'JSON'
        MARKDOWN_ZIP = 'markdown_zip', 'Markdown ZIP'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    export_type = models.CharField(max_length=50, default='articles')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    format = models.CharField(max_length=20, choices=Format.choices, default=Format.CSV)
    
    # Filter parameters
    params = models.JSONField(default=dict)
    
    # Results
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.BigIntegerField(null=True)
    row_count = models.IntegerField(null=True)
    error_message = models.TextField(blank=True)
    
    # Timing
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    
    # User who requested
    requested_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True
    )
    
    class Meta:
        ordering = ['-created_at']
    
    @property
    def download_url(self):
        """Generate download URL if completed."""
        if self.status == self.Status.COMPLETED and self.file_path:
            # Return direct path or signed URL
            return f"/api/exports/{self.id}/download/"
        return None
    
    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
```

### Endpoints

| Method | Path | Action |
|--------|------|--------|
| POST | `/api/exports/` | Create export job |
| GET | `/api/exports/{id}/` | Check status |
| GET | `/api/exports/{id}/download/` | Download file |
| GET | `/api/exports/` | List user's exports |

### Files to Create/Modify

#### `apps/articles/views.py`

```python
class ExportViewSet(viewsets.ModelViewSet):
    """Manage article exports."""
    
    permission_classes = [IsAuthenticated]
    queryset = ExportJob.objects.all()
    http_method_names = ['get', 'post']
    
    def get_queryset(self):
        # Users see only their exports (unless admin)
        if self.request.user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(requested_by=self.request.user)
    
    def create(self, request):
        """Create and queue an export job."""
        serializer = ExportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        export_job = ExportJob.objects.create(
            export_type=serializer.validated_data.get('type', 'articles'),
            format=serializer.validated_data.get('format', 'csv'),
            params=serializer.validated_data.get('filter_params', {}),
            requested_by=request.user,
        )
        
        # Queue Celery task
        try:
            from .tasks import generate_export
            generate_export.delay(str(export_job.id))
        except Exception as e:
            export_job.status = 'failed'
            export_job.error_message = str(e)
            export_job.save()
        
        return Response({
            'export_id': str(export_job.id),
            'status': export_job.status,
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download export file."""
        export_job = self.get_object()
        
        if export_job.status != 'completed':
            return Response(
                {'error': 'Export not ready'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Stream file or redirect to signed URL
        from django.http import FileResponse
        return FileResponse(
            open(export_job.file_path, 'rb'),
            as_attachment=True,
            filename=f"export_{export_job.id}.{export_job.format}"
        )
```

#### `apps/articles/tasks.py`

```python
@shared_task
def generate_export(export_id):
    """Generate export file for articles."""
    import csv
    import json
    from django.conf import settings
    
    export = ExportJob.objects.get(id=export_id)
    export.status = 'running'
    export.started_at = timezone.now()
    export.save()
    
    try:
        # Build queryset from params
        queryset = Article.objects.all()
        params = export.params
        
        if params.get('source_id'):
            queryset = queryset.filter(source_id=params['source_id'])
        if params.get('status'):
            queryset = queryset.filter(processing_status=params['status'])
        # ... more filters
        
        # Generate file
        export_dir = settings.MEDIA_ROOT / 'exports'
        export_dir.mkdir(exist_ok=True)
        file_path = export_dir / f"export_{export.id}.{export.format}"
        
        if export.format == 'csv':
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'title', 'url', 'source', 'score', 'published_date'])
                for article in queryset.iterator():
                    writer.writerow([
                        str(article.id),
                        article.title,
                        article.url,
                        article.source.name if article.source else '',
                        article.total_score,
                        article.published_date,
                    ])
        
        elif export.format == 'json':
            # Similar with JSON serialization
            pass
        
        export.file_path = str(file_path)
        export.file_size = file_path.stat().st_size
        export.row_count = queryset.count()
        export.status = 'completed'
        export.finished_at = timezone.now()
        export.save()
        
    except Exception as e:
        export.status = 'failed'
        export.error_message = str(e)
        export.finished_at = timezone.now()
        export.save()
        raise
```

### Acceptance Criteria

- [ ] POST `/api/exports/` creates job and queues task
- [ ] GET `/api/exports/{id}/` returns status and download_url when ready
- [ ] Download endpoint streams file
- [ ] Large exports don't timeout (async)
- [ ] Users see only their exports

---

## 3B. Metrics Instrumentation

### Objective
- Increment counters/histograms at key operations
- Expose metrics at `/api/core/metrics/`

### Metrics to Instrument

| Metric | Type | Labels | Instrumentation Point |
|--------|------|--------|----------------------|
| `seeds_import_total` | Counter | status, format, mode | SeedBulkImportView.post |
| `seeds_validate_duration_seconds` | Histogram | - | SeedValidateView.post |
| `seeds_discover_total` | Counter | status | SeedDiscoverEntrypointsView.post |
| `seeds_test_crawl_total` | Counter | status | SeedTestCrawlView.post |
| `runs_started_total` | Counter | trigger | RunViewSet.create |
| `runs_completed_total` | Counter | status | finalize_parent_job |
| `articles_exported_total` | Counter | format, status | generate_export task |
| `tagging_assignments_total` | Counter | source | ArticleTagger (future) |

### Files to Modify

#### `apps/seeds/views.py`

```python
from apps.core.metrics import (
    increment_seeds_import,
    observe_validation_duration,
    increment_seeds_discover,
    increment_test_crawl,
)

class SeedBulkImportView(APIView):
    def post(self, request):
        # ... existing logic ...
        
        # Increment metrics
        increment_seeds_import(
            count=len(created),
            status='success',
            format=data.get('format', 'urls'),
            mode=on_duplicate
        )
        
        return Response(...)

class SeedValidateView(APIView):
    def post(self, request, pk):
        with observe_validation_duration():
            # ... existing validation logic ...
        
        return Response(...)
```

### Acceptance Criteria

- [ ] Metrics incremented on each operation
- [ ] Labels correctly applied
- [ ] `/api/core/metrics/` returns Prometheus format
- [ ] Histograms capture timing distributions

---

## 3C. Request ID Verification

### Objective
- Confirm `X-Request-ID` header on all responses
- Same ID in error responses and logs

### Verification Checklist

- [ ] `RequestIDMiddleware` in MIDDLEWARE setting
- [ ] Middleware sets `request.request_id`
- [ ] Response includes `X-Request-ID` header
- [ ] Exception handler uses same request_id
- [ ] Logger filter adds request_id to records

### Files to Verify

#### `config/settings/base.py`

```python
MIDDLEWARE = [
    # ...
    'apps.core.middleware.RequestIDMiddleware',
    # ...
]
```

#### `apps/core/middleware.py`

Already created in Session 23. Verify:
- `process_request` generates/accepts UUID
- `process_response` adds header
- Thread-local storage for logging

### Test Cases

```python
def test_request_id_in_success_response():
    """Success responses include X-Request-ID."""
    response = client.get('/api/articles/')
    assert 'X-Request-ID' in response.headers
    assert len(response.headers['X-Request-ID']) == 36  # UUID format

def test_request_id_in_error_response():
    """Error responses include same X-Request-ID."""
    response = client.get('/api/articles/nonexistent/')
    assert 'X-Request-ID' in response.headers
    assert 'request_id' in response.json()
    assert response.headers['X-Request-ID'] == response.json()['request_id']
```

---

# Implementation Sequence

## Recommended Order

```
┌─────────────────────────────────────────────────────────────────┐
│ Part 1: Seeds Enhancements                                       │
├─────────────────────────────────────────────────────────────────┤
│ 1A. Import normalization + on_duplicate                          │
│ 1B. Validate robots warnings (verify existing)                   │
│ 1C. Test-crawl parameters (verify existing)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Part 2: Sources/Runs/Orchestration                               │
├─────────────────────────────────────────────────────────────────┤
│ 2A. Sources CRUD + test + crawl-now                              │
│ 2B. Runs alias + filters + totals                                │
│ 2C. Orchestration lifecycle in tasks                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Part 3: Articles Export & Observability                          │
├─────────────────────────────────────────────────────────────────┤
│ 3A. ExportJob model + endpoints + task                           │
│ 3B. Metrics instrumentation                                      │
│ 3C. Request ID verification                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Per-Part Verification

After each part:

1. **Run tests**: `pytest apps/{app}/tests/ -v`
2. **Check migrations**: `python manage.py makemigrations --check`
3. **Verify API**: Manual curl/httpie tests
4. **Check metrics**: Scrape `/api/core/metrics/`

---

# Appendix: File Change Summary

| File | Part 1 | Part 2 | Part 3 |
|------|--------|--------|--------|
| `apps/seeds/serializers.py` | ✏️ on_duplicate, update_fields | - | - |
| `apps/seeds/views.py` | ✏️ import logic | - | - |
| `apps/sources/views.py` | - | ✏️ SourceViewSet, actions | - |
| `apps/sources/tasks.py` | - | ✏️ orchestration | - |
| `apps/sources/serializers.py` | - | ✏️ totals | - |
| `apps/articles/models.py` | - | - | ➕ ExportJob |
| `apps/articles/views.py` | - | - | ➕ ExportViewSet |
| `apps/articles/tasks.py` | - | - | ➕ generate_export |
| `apps/core/metrics.py` | - | - | ✏️ instrumentation |
| `apps/core/middleware.py` | - | - | ✅ verify |

Legend: ➕ New file/model | ✏️ Modify | ✅ Verify existing

---

# Quick Reference: Error Codes

| Code | When to Use |
|------|-------------|
| `VALIDATION_ERROR` | Invalid request data |
| `NOT_FOUND` | Resource doesn't exist |
| `DUPLICATE` | Idempotency conflict |
| `SSRF_BLOCKED` | Blocked URL access |
| `NETWORK_ERROR` | External service failure |
| `PERMISSION_DENIED` | Insufficient role |
| `RATE_LIMITED` | Too many requests |

---

**End of Implementation Guide**
