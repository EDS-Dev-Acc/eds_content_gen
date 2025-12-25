# EMCIP Baseline Tests

This document describes how to verify the baseline functionality before and after upgrades.

---

## Prerequisites

```powershell
# Activate virtual environment
cd "I:\EDS Content Generation"
.\venv\Scripts\Activate.ps1

# Verify Django is installed
python -c "import django; print(f'Django {django.VERSION}')"
```

---

## Test 1: Django Server Health

```powershell
# Run migrations
python manage.py migrate

# Start development server (Ctrl+C to stop)
python manage.py runserver

# Expected: Server starts on http://127.0.0.1:8000/
# Admin available at http://127.0.0.1:8000/admin/
```

**Acceptance**: Server starts without errors, admin loads.

---

## Test 2: Model Integrity

```powershell
python scripts/test_models.py
```

**Expected Output**:
```
Testing Source model...
[OK] Created test source
Testing Article model...
[OK] Created test article
All model tests passed!
```

---

## Test 3: Crawler Functionality

```powershell
python scripts/test_crawler.py
```

**Expected Output**:
```
EMCIP Crawler Testing
======================
1. Creating/finding test source...
   [OK] Created test source: Example News (Test)
2. Initializing crawler...
   [OK] Crawler initialized: ScrapyCrawler
3. Starting crawl...
4. Crawl Results:
   - Total links found: X
   - New articles collected: X
   - Duplicates skipped: X
   - Errors: 0
```

**Acceptance**: Crawler runs without exceptions, finds at least 0 links (example.org has minimal links).

---

## Test 4: Pagination Utilities

```powershell
python scripts/test_pagination.py
```

**Expected Output**:
```
✓ Pagination configuration test passed!
✓ URL normalization test passed!
✓ URL deduplicator test passed!
✓ Rate limiter test passed!
✓ URL building test passed!
✓ Next link detection test passed!
All tests completed successfully!
```

---

## Test 5: Article Processing Pipeline

```powershell
python scripts/test_article_processing.py
```

**Expected Output**:
```
EMCIP Article Processing Test
==============================
Article ready: Economic Update: Logistics Corridor Expands
- ID: <uuid>
- Source: Processing Test Source

Processing results:
- Processing status: completed
- Extracted text: (non-empty)
- Total score: XX/100
```

**Acceptance**: Article progresses through extraction → scoring → completed.

---

## Test 6: Celery Task Queue (Optional - requires Redis)

```powershell
# Terminal 1: Start Celery worker
celery -A config worker -l info

# Terminal 2: Test task
python scripts/test_celery_task.py
```

**Note**: If Redis is not available, Celery runs in eager mode by default for development.

---

## Test 7: Content API Endpoints

```powershell
# Start server
python manage.py runserver

# In another terminal or browser:
# GET opportunities
curl http://127.0.0.1:8000/api/content/opportunities/

# GET top articles
curl http://127.0.0.1:8000/api/content/top-articles/
```

**Expected**: JSON responses with article/opportunity data or empty arrays.

---

## Test 8: LLM Integration (Optional - requires API key)

```python
# In Django shell
python manage.py shell

>>> from apps.content.llm import ClaudeClient
>>> client = ClaudeClient()
>>> print(f"Claude available: {client.available}")
# True if ANTHROPIC_API_KEY is set
```

---

## Quick Baseline Validation Script

Save time by running this one-liner:

```powershell
python manage.py migrate; python scripts/test_pagination.py; python scripts/test_article_processing.py
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: django` | Activate venv: `.\venv\Scripts\Activate.ps1` |
| `OperationalError: no such table` | Run `python manage.py migrate` |
| Crawler returns 0 articles | Normal for example.org; test with real news source |
| Translation skipped | Set `ENABLE_TRANSLATION=true` and configure Google API |

---

## Post-Upgrade Verification

After each upgrade phase, re-run all tests above. Key checks:

1. **Schema unchanged**: `python manage.py migrate --check` returns 0
2. **No regressions**: All test scripts pass
3. **Performance**: Processing time per article ≤ baseline

---

*Last Updated: 2025-12-23 - Phase 0*
