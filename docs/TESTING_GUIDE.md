# EMCIP Testing Guide
**Sessions 0-5 Complete Testing Instructions**

Last Updated: 2024-12-20
Status: Sessions 0-5 Complete

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Session 1: Django Project Setup](#session-1-django-project-setup)
4. [Session 2: Core Models](#session-2-core-models)
5. [Session 3: Admin Interfaces](#session-3-admin-interfaces)
6. [Session 4: Basic Crawler](#session-4-basic-crawler)
7. [Session 5: Celery Task Queue](#session-5-celery-task-queue)
8. [Integration Testing](#integration-testing)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python**: 3.11+ (verify: `python --version`)
- **Git**: Any recent version (verify: `git --version`)
- **Redis**: 7.0+ (for Celery testing)
  - Windows: Download from https://github.com/microsoftarchive/redis/releases
  - macOS: `brew install redis`
  - Linux: `sudo apt-get install redis-server`

### Optional Software

- **PostgreSQL**: 15+ (currently using SQLite for development)
- **Web Browser**: For Django admin testing

---

## Environment Setup

### 1. Clone/Navigate to Project

```bash
cd "I:\EDS Content Generation"
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements-minimal.txt
```

Expected packages:
- Django 5.0.1
- djangorestframework 3.14.0
- requests 2.32.5
- beautifulsoup4 4.14.3
- celery 5.6.0
- redis 7.1.0
- whitenoise 6.6.0
- python-dotenv 1.0.0

### 5. Verify Installation

```bash
python manage.py check
```

**Expected output:**
```
System check identified no issues (0 silenced).
```

---

## Session 1: Django Project Setup

### Test 1.1: Django Configuration

```bash
python manage.py check --deploy
```

**Expected:** List of warnings about DEBUG=True (safe to ignore in development)

### Test 1.2: Database Migrations

```bash
python manage.py migrate
```

**Expected output:**
```
Operations to perform:
  Apply all migrations: admin, articles, auth, contenttypes, sessions, sources
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
  Applying sources.0002_crawljob... OK
```

### Test 1.3: Development Server

```bash
python manage.py runserver
```

**Expected:**
- Server starts at http://127.0.0.1:8000/
- No errors in console
- Visit http://127.0.0.1:8000/ in browser - should see default Django page

**Stop the server:** Press `Ctrl+C`

### Test 1.4: Django Shell

```bash
python manage.py shell
```

```python
from django.conf import settings
print(f"DEBUG: {settings.DEBUG}")
print(f"Database: {settings.DATABASES['default']['ENGINE']}")
exit()
```

**Expected output:**
```
DEBUG: True
Database: django.db.backends.sqlite3
```

---

## Session 2: Core Models

### Test 2.1: Run Model Tests

```bash
python scripts/test_models.py
```

**Expected output:**
```
============================================================
EMCIP Model Testing
============================================================

1. Creating test source...
   [OK] Found existing: Business Daily Southeast Asia (businessdaily-sea.example.com)
   - ID: [UUID]
   - Domain: businessdaily-sea.example.com
   - Reputation: 35/100
   - Usage Ratio: 0.0%

2. Creating test article...
   [OK] Created: Foreign Direct Investment Surges 25% in Southeast ...
   - ID: [UUID]
   - Total Score: 91/100
   - Quality Category: high
   - Age: 3 days

3. Updating source statistics...
   [OK] Updated source: 1 articles

4. Testing queries...
   - Total sources: 2
   - Total articles: 2
   - High-quality articles (score ≥70): 1
   - Articles from test source: 1

============================================================
[SUCCESS] All tests passed! Models are working correctly.
============================================================
```

### Test 2.2: Model Validation in Shell

```bash
python manage.py shell
```

```python
from apps.sources.models import Source, CrawlJob
from apps.articles.models import Article

# Check model counts
print(f"Sources: {Source.objects.count()}")
print(f"Articles: {Article.objects.count()}")
print(f"CrawlJobs: {CrawlJob.objects.count()}")

# Test source properties
source = Source.objects.first()
if source:
    print(f"\nSource: {source.name}")
    print(f"  - Usage Ratio: {source.usage_ratio}%")
    print(f"  - Is Healthy: {source.is_healthy}")

# Test article properties
article = Article.objects.first()
if article:
    print(f"\nArticle: {article.title[:50]}")
    print(f"  - Quality Category: {article.quality_category}")
    print(f"  - Age Days: {article.age_days}")
    print(f"  - Is Scored: {article.is_scored}")

exit()
```

### Test 2.3: Database Integrity

```bash
python manage.py dbshell
```

**SQLite commands:**
```sql
.tables
-- Should show: articles, auth_*, crawl_jobs, django_*, sources

SELECT COUNT(*) FROM sources;
SELECT COUNT(*) FROM articles;
SELECT COUNT(*) FROM crawl_jobs;

.quit
```

---

## Session 3: Admin Interfaces

### Test 3.1: Create Superuser (if not exists)

```bash
python scripts/create_superuser.py
```

**Expected output:**
```
[INFO] Superuser 'admin' already exists.
       Username: admin
       Password: admin

You can now access the admin at:
  http://localhost:8000/admin/
```

**Credentials:**
- Username: `admin`
- Password: `admin`

### Test 3.2: Access Admin Interface

1. **Start server:**
   ```bash
   python manage.py runserver
   ```

2. **Visit:** http://localhost:8000/admin/

3. **Login:** admin / admin

**Expected:** Django admin dashboard with:
- Authentication and Authorization
- Articles (with article count)
- Sources (with source count and crawl jobs)

### Test 3.3: Test SourceAdmin

**In the admin:**

1. Click **"Sources"**

**Verify List Display:**
- Name column
- Domain column
- Source Type column
- Reputation badge (color-coded: green ≥35, orange ≥25, red <25)
- Status
- Total articles collected
- Usage ratio (color-coded)
- Last crawled (time ago format)

**Test Filters:**
- Click "Source type" filter → should see options
- Click "Status" filter → should see Active/Inactive/etc.
- Click "Discovery method" filter

**Test Search:**
- Enter source name in search box
- Should filter results

**Test Detail View:**
1. Click on a source
2. Should see organized fieldsets:
   - Basic Information
   - Geographic & Topic Focus
   - Quality & Reputation
   - Crawling Configuration (collapsed)
   - Statistics (collapsed)
   - Discovery & Management (collapsed)
   - System Fields (collapsed)

**Test Actions:**
1. Select a source (checkbox)
2. Choose "Mark as inactive" from action dropdown
3. Click "Go"
4. Verify source status changed

### Test 3.4: Test ArticleAdmin

1. Click **"Articles"** in admin sidebar

**Verify List Display:**
- Title (truncated to 60 chars)
- Source
- Primary region
- Primary topic
- Score badge (color-coded)
- Quality badge (HIGH/MED/LOW with colors)
- Processing status
- AI detected badge
- Published date

**Test Filters:**
- Processing status filter
- Primary region filter
- Primary topic filter
- AI content detected filter
- Published date filter (shows date hierarchy)

**Test Search:**
- Search by title
- Search by URL
- Search by author

**Test Detail View:**
1. Click on an article
2. Verify fieldsets are organized logically
3. Check readonly fields (ID, timestamps, scores)

**Test Actions:**
1. Select article(s)
2. Try "Mark for rescoring" action
3. Verify processing_status changes

---

## Session 4: Basic Crawler

### Test 4.1: Run Crawler Test

```bash
python scripts/test_crawler.py
```

**Expected output:**
```
======================================================================
EMCIP Crawler Testing
======================================================================

1. Creating/finding test source...
   [OK] Created test source: Example News (Test)
   - Domain: example.org
   - URL: https://example.org
   - Crawler Type: scrapy

2. Initializing crawler...
   [OK] Crawler initialized: ScrapyCrawler

3. Starting crawl...
   (This may take a few moments...)

4. Crawl Results:
   - Total links found: 0
   - New articles collected: 0
   - Duplicates skipped: 0
   - Errors: 0

6. Updated Source Statistics:
   - Total articles collected: 0
   - Last crawled: [timestamp]
   - Error count: 0

======================================================================
[SUCCESS] Crawler test complete!
======================================================================
```

**Note:** example.org is a simple site with no articles. This is expected.

### Test 4.2: Manual Crawler Test with Real Source

**In Django shell:**
```bash
python manage.py shell
```

```python
from apps.sources.models import Source
from apps.sources.crawlers import get_crawler

# Create a test source (you can use any simple news blog)
# For testing, we'll use example.org
source = Source.objects.get_or_create(
    domain="example.org",
    defaults={
        "name": "Example Site",
        "url": "https://example.org",
        "status": "active",
        "crawler_type": "scrapy"
    }
)[0]

# Get crawler
crawler = get_crawler(source)
print(f"Crawler type: {crawler.__class__.__name__}")

# Run crawl
results = crawler.crawl()
print(f"\nResults:")
print(f"  Total found: {results['total_found']}")
print(f"  New articles: {results['new_articles']}")
print(f"  Duplicates: {results['duplicates']}")
print(f"  Errors: {results['errors']}")

# Check source was updated
source.refresh_from_db()
print(f"\nSource last crawled: {source.last_crawled_at}")

exit()
```

### Test 4.3: Verify Crawler Components

```bash
python manage.py shell
```

```python
from apps.sources.crawlers import get_crawler, BaseCrawler, ScrapyCrawler
from apps.sources.models import Source

# Verify imports work
print("✓ BaseCrawler imported")
print("✓ ScrapyCrawler imported")
print("✓ get_crawler imported")

# Test factory function
source = Source.objects.first()
if source:
    crawler = get_crawler(source)
    print(f"✓ Crawler created: {type(crawler).__name__}")

    # Test crawler has required methods
    assert hasattr(crawler, 'crawl'), "Crawler missing crawl method"
    assert hasattr(crawler, '_is_duplicate'), "Crawler missing _is_duplicate"
    assert hasattr(crawler, '_save_article'), "Crawler missing _save_article"
    print("✓ All crawler methods present")

exit()
```

---

## Session 5: Celery Task Queue

### Test 5.1: Verify Celery Installation

```bash
python -c "import celery; print(f'Celery version: {celery.__version__}')"
python -c "import redis; print(f'Redis version: {redis.__version__}')"
```

**Expected:**
```
Celery version: 5.6.0
Redis version: 7.1.0
```

### Test 5.2: Verify Task Definition

```bash
python manage.py shell
```

```python
from apps.sources.tasks import crawl_source, crawl_all_active_sources

print("✓ crawl_source task imported")
print("✓ crawl_all_active_sources task imported")

# Verify tasks are registered
from config.celery import app
registered = list(app.tasks.keys())
print(f"\nRegistered tasks: {len(registered)}")
print("Task names:")
for task_name in sorted(registered):
    if 'crawl' in task_name.lower():
        print(f"  - {task_name}")

exit()
```

### Test 5.3: Verify CrawlJob Model

```bash
python manage.py shell
```

```python
from apps.sources.models import CrawlJob, Source

# Check model works
print(f"CrawlJob count: {CrawlJob.objects.count()}")

# Create a test crawl job
source = Source.objects.first()
if source:
    job = CrawlJob.objects.create(
        source=source,
        status='pending'
    )
    print(f"✓ Created test CrawlJob: {job.id}")
    print(f"  Status: {job.status}")
    print(f"  Source: {job.source.name}")

    # Test duration property
    from django.utils import timezone
    job.started_at = timezone.now()
    job.completed_at = timezone.now()
    print(f"  Duration: {job.duration}")

    # Clean up
    job.delete()
    print("✓ Test job deleted")

exit()
```

### Test 5.4: Test Celery with Redis (Full Integration)

**Prerequisites:**
1. Redis must be running
2. Celery worker must be running

**Step 1: Start Redis**

**Windows:**
```bash
# Download Redis from: https://github.com/microsoftarchive/redis/releases
# Extract and run:
redis-server.exe
```

**macOS/Linux:**
```bash
redis-server
# Or if installed via package manager:
sudo systemctl start redis
# Or:
brew services start redis
```

**Verify Redis is running:**
```bash
redis-cli ping
```

**Expected output:** `PONG`

**Step 2: Start Celery Worker**

Open a **NEW terminal window**, activate venv, and run:

**Windows:**
```bash
cd "I:\EDS Content Generation"
venv\Scripts\activate
celery -A config worker --loglevel=info --pool=solo
```

**macOS/Linux:**
```bash
cd "/path/to/EDS Content Generation"
source venv/bin/activate
celery -A config worker --loglevel=info
```

**Expected output:**
```
-------------- celery@HOSTNAME v5.6.0
---- **** -----
--- * ***  * -- Windows-10.0 2024-12-20
-- * - **** ---
- ** ---------- [config]
- ** ---------- .> app:         emcip:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 1 (solo)
-- ******* ---- .> task events: OFF

[tasks]
  . apps.sources.tasks.crawl_all_active_sources
  . apps.sources.tasks.crawl_source

[2024-12-20 ...] INFO/MainProcess] Connected to redis://localhost:6379/0
[2024-12-20 ...] INFO/MainProcess] Ready to accept tasks
```

**Leave this terminal open!**

**Step 3: Queue a Task**

In your **ORIGINAL terminal**, run:

```bash
python scripts/test_celery_task.py
```

**Expected output:**
```
======================================================================
EMCIP Celery Task Testing
======================================================================

1. Finding test source...
   [OK] Found source: Example News (Test)
   - ID: [UUID]
   - Domain: example.org

2. Queuing crawl task...
   [OK] Task queued!
   - Task ID: [UUID]
   - Task state: PENDING

3. Checking task status...
   (Waiting 3 seconds...)
   - Current state: SUCCESS
   [SUCCESS] Task completed!
   - New articles: 0
   - Duplicates: 0

4. Checking CrawlJob records...
   Recent crawl jobs for Example News (Test):
   - completed at [timestamp]
     New: 0, Duplicates: 0
```

**In the Celery worker terminal**, you should see:
```
[2024-12-20 ...] INFO/MainProcess] Task apps.sources.tasks.crawl_source[...] received
[2024-12-20 ...] INFO/MainProcess] Starting crawl task for Example News (Test)
[2024-12-20 ...] INFO/MainProcess] Crawl complete for Example News (Test): 0 new articles
[2024-12-20 ...] INFO/MainProcess] Task apps.sources.tasks.crawl_source[...] succeeded
```

### Test 5.5: Manual Task Queue Test

**With Redis and Celery worker running**, in Django shell:

```bash
python manage.py shell
```

```python
from apps.sources.tasks import crawl_source
from apps.sources.models import Source, CrawlJob

# Get a source
source = Source.objects.first()
print(f"Testing with source: {source.name}")

# Queue the task
result = crawl_source.delay(str(source.id))
print(f"Task queued: {result.id}")
print(f"State: {result.state}")

# Wait a bit
import time
time.sleep(5)

# Check result
print(f"Final state: {result.state}")
if result.ready():
    print(f"Result: {result.get()}")

# Check CrawlJob was created
jobs = CrawlJob.objects.filter(source=source).order_by('-created_at')[:1]
if jobs:
    job = jobs[0]
    print(f"\nCrawlJob created:")
    print(f"  Status: {job.status}")
    print(f"  New articles: {job.new_articles}")
    print(f"  Task ID: {job.task_id}")

exit()
```

---

## Integration Testing

### Integration Test 1: Complete Workflow

**This tests the entire pipeline from source creation to async crawling.**

```bash
python manage.py shell
```

```python
from apps.sources.models import Source, CrawlJob
from apps.articles.models import Article
from apps.sources.tasks import crawl_source

# 1. Create a new test source
source, created = Source.objects.get_or_create(
    domain="test-integration.example.com",
    defaults={
        "name": "Integration Test Source",
        "url": "https://example.org",  # Simple test site
        "status": "active",
        "reputation_score": 25,
        "crawler_config": {"max_articles": 5}
    }
)
print(f"1. Source: {source.name} (created: {created})")

# 2. Queue crawl task (requires Celery worker running)
result = crawl_source.delay(str(source.id))
print(f"2. Task queued: {result.id}")

# 3. Wait for completion
import time
for i in range(10):
    if result.ready():
        break
    print(f"   Waiting... ({i+1}s)")
    time.sleep(1)

# 4. Check results
if result.ready():
    task_result = result.get()
    print(f"3. Task completed: {task_result['success']}")
    print(f"   New articles: {task_result['results']['new_articles']}")
else:
    print("3. Task still running or failed")

# 5. Verify CrawlJob was created
jobs = CrawlJob.objects.filter(source=source).order_by('-created_at')
if jobs.exists():
    job = jobs.first()
    print(f"4. CrawlJob status: {job.status}")
    print(f"   Duration: {job.duration}")
else:
    print("4. No CrawlJob found!")

# 6. Check source was updated
source.refresh_from_db()
print(f"5. Source last crawled: {source.last_crawled_at}")
print(f"   Total articles: {source.total_articles_collected}")

exit()
```

### Integration Test 2: Admin Workflow

**Test the full admin experience:**

1. **Start server:**
   ```bash
   python manage.py runserver
   ```

2. **Open admin:** http://localhost:8000/admin/

3. **Create a new source:**
   - Click "Sources" → "Add Source"
   - Fill in:
     - Name: "Test News Site"
     - Domain: "testnews.example.com"
     - URL: "https://example.org"
     - Source Type: News Website
     - Status: Active
     - Reputation Score: 30
   - Save

4. **Verify source appears in list**
   - Should see green/orange/red reputation badge
   - Last crawled should be empty

5. **Manually trigger crawl** (if Celery running):
   ```python
   # In Django shell
   from apps.sources.tasks import crawl_source
   from apps.sources.models import Source

   source = Source.objects.get(domain="testnews.example.com")
   crawl_source.delay(str(source.id))
   ```

6. **Refresh source page in admin**
   - "Last crawled" should be populated
   - May see CrawlJobs in the related objects

7. **Check Articles:**
   - Click "Articles" in admin
   - Should see any collected articles (may be 0 for example.org)

---

## Troubleshooting

### Issue: ImportError when running scripts

**Symptom:**
```
ModuleNotFoundError: No module named 'apps'
```

**Solution:**
Ensure you're running scripts from project root and Django environment is set up:
```bash
cd "I:\EDS Content Generation"
python scripts/test_models.py  # Not: python test_models.py
```

### Issue: Database is locked

**Symptom:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
Close all Django shells and server instances:
```bash
# Stop any running manage.py processes
# Close all terminal windows running Django
# Then try again
```

### Issue: Celery worker won't start

**Symptom:**
```
Error: [WinError 10061] No connection could be made
```

**Solution:**
Redis isn't running. Start Redis first:
```bash
redis-server.exe  # Windows
# Or
redis-server      # macOS/Linux
```

### Issue: Tasks stay in PENDING state

**Symptom:**
Tasks are queued but never execute

**Solutions:**
1. **Check Celery worker is running:**
   ```bash
   # Should see "Ready to accept tasks" in worker terminal
   ```

2. **Check Redis is accessible:**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

3. **Check task is registered:**
   ```bash
   python manage.py shell
   from config.celery import app
   print(list(app.tasks.keys()))
   # Should see apps.sources.tasks.crawl_source
   ```

### Issue: Admin shows "No module named X"

**Symptom:**
```
ImportError: No module named 'rest_framework'
```

**Solution:**
Install missing dependencies:
```bash
pip install -r requirements-minimal.txt
```

### Issue: Migrations not applying

**Symptom:**
```
django.db.utils.OperationalError: no such table: sources
```

**Solution:**
Run migrations:
```bash
python manage.py migrate
```

---

## Test Checklist

Use this checklist to verify all functionality:

### Session 1: Django Setup
- [ ] `python manage.py check` passes
- [ ] `python manage.py migrate` completes
- [ ] `python manage.py runserver` starts without errors
- [ ] Can access http://127.0.0.1:8000/ in browser

### Session 2: Models
- [ ] `python scripts/test_models.py` completes successfully
- [ ] Source model properties work (usage_ratio, is_healthy)
- [ ] Article model properties work (quality_category, age_days)
- [ ] Can query models in shell without errors

### Session 3: Admin
- [ ] Can login to admin with admin/admin
- [ ] SourceAdmin displays all columns correctly
- [ ] SourceAdmin filters work
- [ ] SourceAdmin actions work (mark inactive/active)
- [ ] ArticleAdmin displays all columns correctly
- [ ] ArticleAdmin filters work
- [ ] Color-coded badges display correctly
- [ ] Can create/edit/delete sources and articles

### Session 4: Crawler
- [ ] `python scripts/test_crawler.py` completes
- [ ] Crawler successfully fetches pages
- [ ] Source statistics update after crawl
- [ ] Can manually run crawler in shell
- [ ] Duplicate detection works

### Session 5: Celery
- [ ] Celery and Redis installed
- [ ] Can import tasks without errors
- [ ] CrawlJob model works
- [ ] Can start Celery worker (with Redis running)
- [ ] `python scripts/test_celery_task.py` succeeds
- [ ] CrawlJob records are created
- [ ] Tasks execute and complete

### Integration
- [ ] Complete workflow test passes
- [ ] Admin workflow test passes
- [ ] Can create source → crawl → see results

---

## Next Steps After Testing

Once all tests pass:

1. **Review the admin interface** - familiarize yourself with the UI
2. **Add real news sources** - test with actual websites
3. **Monitor crawler performance** - check logs and CrawlJob records
4. **Experiment with Celery** - try scheduling tasks
5. **Prepare for Session 6** - Text extraction (newspaper3k)

---

## Getting Help

If tests fail:

1. **Check the Troubleshooting section** above
2. **Review error messages carefully** - they usually indicate the problem
3. **Check PROJECT_STATE.md** - ensure you're on the right session
4. **Review session-specific code** - in apps/sources/, apps/articles/
5. **Check logs** - in terminal output and Celery worker logs

---

**End of Testing Guide for Sessions 0-5**

For questions about the next sessions (6+), refer to claude.md for implementation guidance.
