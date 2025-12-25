# Operator Console MVP - Testing Guide

## Current Test Status

| Phase | Test File | Tests | Status |
|-------|-----------|-------|--------|
| 10.0 | scripts/test_integration.py | 30 | ✅ Pass |
| 10.1 | scripts/test_auth.py | 10 | ✅ Pass |
| 10.2 | scripts/test_runs.py | 15 | ✅ Pass |
| 10.3 | scripts/test_schedules_api.py | 15 | ✅ Pass |
| 10.4 | scripts/test_seeds_api.py | 18 | ✅ Pass |
| **Total** | | **88** | ✅ |

---

## Test Environment Setup

### Prerequisites
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Environment variables
set DJANGO_SETTINGS_MODULE=config.settings.development
```

### Database
```bash
# Run migrations
python manage.py migrate

# Create test superuser
python manage.py createsuperuser --username admin --email admin@test.com
```

---

## Running Tests

### Quick Test Commands
```bash
# Phase 10.0 - Integration tests (30 tests)
python scripts/test_integration.py

# Phase 10.1 - Auth tests (10 tests)
python scripts/test_auth.py

# Phase 10.2 - Runs tests (15 tests)
python scripts/test_runs.py

# Phase 10.3 - Schedules tests (15 tests)
python scripts/test_schedules_api.py
```

### Full Test Suite
```bash
# Run all tests
pytest

# With coverage
pytest --cov=apps --cov-report=html

# Verbose output
pytest -v
```

### By App
```bash
# Auth tests (Phase 10.1)
pytest apps/core/tests/test_auth.py -v

# Runs tests (Phase 10.2)
pytest apps/sources/tests/test_runs.py -v

# Schedules tests (Phase 10.3)
pytest apps/sources/tests/test_schedules.py -v

# Seeds tests (Phase 10.4)
pytest apps/seeds/tests/ -v

# Articles tests (Phase 10.5)
pytest apps/articles/tests/test_viewer.py -v

# LLM Settings tests (Phase 10.6)
pytest apps/content/tests/test_settings.py -v
```

### By Marker
```bash
# Unit tests only
pytest -m unit

# Integration tests
pytest -m integration

# API tests
pytest -m api
```

---

## Test Structure

### Directory Layout
```
apps/
├── core/
│   └── tests/
│       ├── __init__.py
│       ├── test_auth.py          # JWT auth tests
│       ├── test_profile.py       # OperatorProfile tests
│       └── conftest.py           # Fixtures
├── sources/
│   └── tests/
│       ├── test_runs.py          # Run API tests
│       ├── test_schedules.py     # Schedule API tests
│       └── test_models.py        # Model tests
├── seeds/
│   └── tests/
│       ├── test_models.py        # Seed model tests
│       ├── test_api.py           # Seeds API tests
│       └── test_promotion.py     # Promotion wizard tests
├── articles/
│   └── tests/
│       ├── test_viewer.py        # 7-tab viewer tests
│       ├── test_related.py       # Related model tests
│       └── test_api.py           # Article API tests
└── content/
    └── tests/
        ├── test_settings.py      # LLM settings tests
        └── test_llm.py           # Existing LLM tests
```

---

## Common Test Fixtures

### conftest.py
```python
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

@pytest.fixture
def auth_client(user):
    """API client with JWT authentication."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client

@pytest.fixture
def source(db):
    """Create test source."""
    from apps.sources.models import Source
    return Source.objects.create(
        name='Test Source',
        domain='example.com',
        url='https://example.com',
        source_type='news_site',
        status='active',
        reputation_score=75
    )

@pytest.fixture
def article(db, source):
    """Create test article."""
    from apps.articles.models import Article
    return Article.objects.create(
        source=source,
        url='https://example.com/article/1',
        title='Test Article',
        extracted_text='Test content here.',
        processing_status='completed',
        total_score=80
    )

@pytest.fixture
def seed(db, user):
    """Create test seed."""
    from apps.seeds.models import Seed
    return Seed.objects.create(
        url='https://newssite.com',
        domain='newssite.com',
        status='pending',
        discovered_by=user
    )
```

---

## Test Categories

### Unit Tests
- Model validation
- Serializer validation
- Utility functions
- Business logic

### Integration Tests
- Database operations
- Celery task execution
- LLM client mocking

### API Tests
- Endpoint authentication
- Request validation
- Response format
- Error handling
- Pagination

---

## Key Test Cases by Phase

### Phase 10.1: Auth
- [ ] Login with valid credentials returns tokens
- [ ] Login with invalid credentials returns 401
- [ ] Refresh token generates new access token
- [ ] Protected endpoint rejects without token
- [ ] /api/auth/me/ returns user profile
- [ ] OperatorProfile created on user creation

### Phase 10.2: Runs
- [ ] List runs returns paginated results
- [ ] Filter runs by status
- [ ] Filter runs by source
- [ ] Start run creates CrawlJob
- [ ] Start run with overrides applies them
- [ ] Multi-source run creates CrawlJobSourceResults
- [ ] Cancel run updates status

### Phase 10.3: Schedules
- [ ] Create schedule creates PeriodicTask
- [ ] Update schedule updates crontab
- [ ] Delete schedule removes PeriodicTask
- [ ] Run-now triggers immediate crawl
- [ ] Pause-all disables all schedules
- [ ] History returns past runs

### Phase 10.4: Seeds
- [ ] Create seed extracts domain
- [ ] Duplicate URL rejected
- [ ] Bulk import handles mixed results
- [ ] Validate checks crawlability
- [ ] Promote creates Source with config
- [ ] Promoted seed links to Source

### Phase 10.5: Article Viewer
- [ ] Detail returns all related data
- [ ] Raw capture endpoint works
- [ ] Scores endpoint returns breakdown
- [ ] LLM artifacts endpoint works
- [ ] Images endpoint works
- [ ] Reprocess triggers tasks

### Phase 10.6: LLM Settings
- [ ] Get settings returns current config
- [ ] Patch settings updates values
- [ ] Budget enforcement works
- [ ] Usage endpoint returns stats

---

## Mocking External Services

### Claude API
```python
from unittest.mock import patch, MagicMock

@patch('apps.content.llm.requests.post')
def test_claude_call(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        'content': [{'type': 'text', 'text': 'response'}],
        'usage': {'input_tokens': 100, 'output_tokens': 50}
    }
    # ... test code
```

### Celery Tasks
```python
from celery import current_app

@pytest.fixture(autouse=True)
def celery_eager():
    """Run Celery tasks synchronously in tests."""
    current_app.conf.task_always_eager = True
    yield
    current_app.conf.task_always_eager = False
```

---

## Coverage Goals

| App | Target | Current |
|-----|--------|---------|
| core (auth) | 90% | - |
| sources (runs/schedules) | 85% | - |
| seeds | 90% | - |
| articles (viewer) | 85% | - |
| content (settings) | 90% | - |

---

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7
        ports: [6379:6379]
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --cov=apps --cov-fail-under=80
```
