# Control Center Troubleshooting Guide

This document catalogs known issues, their symptoms, root causes, and fixes encountered while developing the Crawl Control Center feature. Use this as a primer before debugging.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Environment Issues](#development-environment-issues)
3. [Task Execution Issues](#task-execution-issues)
4. [Template & Frontend Issues](#template-frontend-issues)
5. [Model & Database Issues](#model-database-issues)
6. [Quick Reference Commands](#quick-reference-commands)

---

## Architecture Overview

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Django | Web server, API, SSE events | `manage.py runserver 8000` |
| Celery | Async task execution | `celery -A config.celery worker` |
| Redis | Message broker + result backend | `localhost:6379` |
| SQLite | Database | `db.sqlite3` |

### Key Files

- **Views**: `apps/core/console_views.py` - All Control Center views
- **URLs**: `apps/core/console_urls.py` - Console URL routing
- **Tasks**: `apps/sources/tasks.py` - Crawl tasks (`crawl_source`, `run_crawl_job`)
- **Models**: `apps/sources/models.py` - `CrawlJob`, `CrawlJobSourceResult`, `Source`, `CrawlJobSeed`
- **Templates**: `templates/console/control_center/` - HTMX templates

### Task Flow

```
User clicks "Start Run"
    → ControlCenterStartView.post()
    → _launch_job() helper
    → crawl_source.delay(source_id, crawl_job_id=job.id)  # Single source
    → Celery worker picks up task from 'crawl' queue
    → Task updates CrawlJob status via SSE events
```

---

## Development Environment Issues

### Issue 1: Celery Worker Not Processing Tasks

**Symptoms:**
- Click "Start Run" but nothing happens
- Job stays in "Queued" or "Running" with no progress
- No task output in Celery terminal

**Root Cause:**
Celery worker not listening to the `crawl` queue. By default, Celery only listens to `default` queue.

**Fix:**
```powershell
# WRONG - only listens to 'default' queue
celery -A config.celery worker -l INFO --pool=solo

# CORRECT - listens to both queues
celery -A config.celery worker -l INFO --pool=solo -Q default,crawl
```

**Why it happens:**
The `crawl_source` task is routed to the `crawl` queue via `task_routes` in `config/celery.py`:
```python
task_routes = {
    'apps.sources.tasks.crawl_source': {'queue': 'crawl'},
}
```

---

### Issue 2: Django Not Picking Up Code Changes

**Symptoms:**
- Made code fix but same error persists
- Logs show old behavior despite file changes

**Root Cause:**
Django was started with `--noreload` flag, disabling auto-reload.

**Fix:**
```powershell
# Start WITHOUT --noreload
python manage.py runserver 8000
```

**Verification:**
Check Django logs for reload message:
```
INFO autoreload I:\...\console_views.py changed, reloading.
```

---

### Issue 3: Terminal Conflicts Killing Celery

**Symptoms:**
- Running a command kills Celery worker
- See "Warm shutdown (MainProcess)" unexpectedly
- Multiple terminals getting confused

**Root Cause:**
VS Code terminal routing. Commands sometimes go to wrong terminal.

**Prevention:**
1. Start Celery with `isBackground=true`
2. Use dedicated terminal IDs
3. Kill and restart if conflicts occur

**Recovery:**
```powershell
# Kill all Celery processes
taskkill /IM celery.exe /F

# Kill all Python processes (nuclear option)
taskkill /IM python.exe /F

# Clean restart
python manage.py runserver 8000
celery -A config.celery worker -l INFO --pool=solo -Q default,crawl
```

---

### Issue 4: Stale Tasks in Redis Queue

**Symptoms:**
- Old tasks keep retrying with wrong parameters
- Error messages reference old job IDs
- Tasks fail immediately after Celery starts

**Root Cause:**
Failed tasks with retry configured stay in Redis queue.

**Fix:**
```python
# Purge all pending tasks
from config.celery import app
app.control.purge()
```

Or via command line:
```powershell
celery -A config.celery purge -f
```

---

## Task Execution Issues

### Issue 5: "Source None not found"

**Symptoms:**
```
ERROR tasks Source None not found
Task succeeded with: {'success': False, 'error': 'Source not found'}
```

**Root Cause:**
`CrawlJob.source` is `None` for the job being launched. This can happen when:
1. Clone view doesn't copy `source` field
2. Job was created without selecting a source

**Location of Bug:**
`apps/core/console_views.py` - `ControlCenterCloneView` (line ~2191)

**Fix:**
Ensure clone view copies the source:
```python
clone = CrawlJob.objects.create(
    # ... other fields ...
    source=original.source,  # <-- This was missing
)
```

---

### Issue 6: "CrawlJobSourceResult matching query does not exist"

**Symptoms:**
```
ERROR tasks Error crawling source xxx: CrawlJobSourceResult matching query does not exist.
```

**Root Cause:**
Task was called with `parent_job_id` instead of `crawl_job_id` for a single-source job.

**Explanation:**
- `crawl_job_id`: Use existing `CrawlJob` record directly (single-source jobs)
- `parent_job_id`: Expects `CrawlJobSourceResult` records to exist (multi-source jobs)

**Location of Bug:**
`apps/core/console_views.py` - `_launch_job()` helper (line ~1518)

**Fix:**
```python
# In _launch_job() for single-source jobs:
# WRONG:
crawl_source.delay(str(job.source_id), parent_job_id=str(job.id))

# CORRECT:
crawl_source.delay(str(job.source_id), crawl_job_id=str(job.id))
```

**Task Logic Reference** (`apps/sources/tasks.py`):
```python
def crawl_source(self, source_id, crawl_job_id=None, parent_job_id=None, ...):
    if crawl_job_id:
        # Use existing CrawlJob record directly
        crawl_job = CrawlJob.objects.get(id=crawl_job_id)
    elif parent_job_id:
        # Look up CrawlJobSourceResult (for multi-source jobs)
        parent_job = CrawlJob.objects.get(id=parent_job_id)
        source_result = CrawlJobSourceResult.objects.get(
            crawl_job=parent_job, source=source
        )  # <-- Fails if no CrawlJobSourceResult exists
```

---

## Template & Frontend Issues

### Issue 7: SSE UUID Serialization Error

**Symptoms:**
```
TypeError: Object of type UUID is not JSON serializable
```

**Root Cause:**
Passing UUID objects directly to `json.dumps()` in SSE event data.

**Fix:**
Always convert UUIDs to strings:
```python
# WRONG:
data = {'job_id': job.id}

# CORRECT:
data = {'job_id': str(job.id)}
```

---

### Issue 8: Alpine.js Template Escaping

**Symptoms:**
- JavaScript errors in browser console
- Alpine.js directives not working
- Seeing `&quot;` or `&#x27;` in rendered HTML

**Root Cause:**
Django's template auto-escaping conflicts with Alpine.js syntax.

**Fix:**
Use `{% verbatim %}` tags or the `|safe` filter carefully:
```html
{% verbatim %}
<div x-data="{ open: false }" @click="open = !open">
{% endverbatim %}
```

Or for dynamic data:
```html
<div x-data='{{ alpine_data|escapejs }}'>
```

---

### Issue 9: Missing `messages` Import

**Symptoms:**
```
NameError: name 'messages' is not defined
```

**Root Cause:**
Django messages framework not imported in view file.

**Fix:**
```python
from django.contrib import messages
```

---

### Issue 10: Template Field Name Mismatches

**Symptoms:**
- Template shows empty values
- `VariableDoesNotExist` errors (if debug enabled)
- Silently displays nothing

**Common Mismatches Found:**

| Template Used | Correct Field |
|---------------|---------------|
| `job.max_pages` | `job.max_pages_run` |
| `job.new_count` | `job.new_articles` |
| `job.duplicate_count` | `job.duplicates` |
| `job.error_count` | `job.errors` |
| `job.completed` | `job.completed_at` |
| `job.seeds.all` | `job.job_seeds.all` |

**Prevention:**
Check model definition in `apps/sources/models.py` before using in templates.

---

## Model & Database Issues

### Issue 11: Seed Query Returns Empty

**Symptoms:**
- Seeds panel shows no seeds
- `job.seeds.all` returns empty queryset

**Root Cause:**
Wrong related_name. The model uses `job_seeds`, not `seeds`.

**Model Definition:**
```python
class CrawlJobSeed(models.Model):
    job = models.ForeignKey(
        CrawlJob, 
        on_delete=models.CASCADE, 
        related_name='job_seeds'  # <-- Use this
    )
```

**Fix:**
```python
# WRONG:
job.seeds.all()

# CORRECT:
job.job_seeds.all()
```

---

### Issue 12: Duplicate Class Definitions

**Symptoms:**
- Code fix doesn't work
- Different behavior than expected
- Python uses last definition silently

**Root Cause:**
Same class defined twice in file. Python uses the LAST definition.

**Example Found:**
`ControlCenterCloneView` was defined at both line 1540 and line 2140 in `console_views.py`.

**Detection:**
```powershell
# Search for duplicate class names
Select-String -Path "apps/core/console_views.py" -Pattern "class ControlCenterCloneView"
```

**Fix:**
Remove duplicate, keep only one (usually the more complete version).

---

## Quick Reference Commands

### Clean Restart
```powershell
# Kill everything
taskkill /IM celery.exe /F
taskkill /IM python.exe /F

# Start Django
cd "I:\EDS Content Generation"
python manage.py runserver 8000

# Start Celery (new terminal)
celery -A config.celery worker -l INFO --pool=solo -Q default,crawl
```

### Reset a Job to Draft
```python
from apps.sources.models import CrawlJob
job = CrawlJob.objects.get(id='<job-uuid>')
job.status = 'draft'
job.started_at = None
job.completed_at = None
job.task_id = ''
job.pages_crawled = 0
job.new_articles = 0
job.duplicates = 0
job.errors = 0
job.save()
```

### Purge Task Queue
```python
from config.celery import app
app.control.purge()
```

### Check Job State
```python
from apps.sources.models import CrawlJob
job = CrawlJob.objects.get(id='<job-uuid>')
print(f"Status: {job.status}")
print(f"Source: {job.source}")
print(f"Source ID: {job.source_id}")
print(f"Is multi-source: {job.is_multi_source}")
print(f"Source results: {job.source_results.count()}")
print(f"Seeds: {job.job_seeds.count()}")
```

### Verify Celery is Processing
Look for in Celery output:
```
[INFO/MainProcess] celery@HOSTNAME ready.
[INFO/MainProcess] Task apps.sources.tasks.crawl_source[...] received
```

---

## Debugging Checklist

When a job doesn't run:

- [ ] Is Django running? Check http://127.0.0.1:8000/
- [ ] Is Celery running with `-Q default,crawl`?
- [ ] Did Django reload after code changes? Check for "changed, reloading" message
- [ ] Does the job have a source? `job.source_id` should not be None
- [ ] Is it single or multi-source? Check `job.is_multi_source`
- [ ] Are there stale tasks in queue? Purge if needed
- [ ] Check Celery logs for "Task received" message
- [ ] Check for error messages after "Task received"

---

## Common Error → Fix Quick Reference

| Error | Likely Fix |
|-------|-----------|
| "Source None not found" | Clone view missing `source=original.source` |
| "CrawlJobSourceResult...does not exist" | Use `crawl_job_id` not `parent_job_id` for single-source |
| Task not received | Start Celery with `-Q default,crawl` |
| Old code still running | Restart Django or ensure auto-reload enabled |
| UUID not JSON serializable | Wrap with `str()` |
| Empty seeds list | Use `job.job_seeds.all()` not `job.seeds.all()` |
| messages not defined | Add `from django.contrib import messages` |

---

*Last updated: December 26, 2025*
