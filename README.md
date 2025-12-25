# EMCIP - Emerging Markets Content Intelligence Platform

An automated content generation system that crawls emerging market news sources, analyzes content using AI, and generates publication-ready blog posts.

## 🎯 Project Overview

EMCIP automates the process of:
- Crawling 30-100 articles daily from emerging market sources
- Translating and scoring content using multiple criteria
- Using Claude API to identify content opportunities
- Generating 6-8 publication-ready blog posts weekly (75-85% complete)
- Learning from source quality and usage patterns

## 🏗️ Tech Stack

- **Backend**: Python 3.11+ / Django 5.0+
- **Database**: PostgreSQL 15+
- **Task Queue**: Celery 5.3+ / Redis 7+
- **Storage**: AWS S3 (or MinIO for local)
- **LLM**: Claude Sonnet 4 (primary), GPT-4 (fallback)
- **Translation**: Google Translate API
- **Crawling**: Scrapy, Playwright (hybrid fetching)

## 📦 Architecture (Phases 2-8)

### Phase 2: Interface Abstractions
Clean separation of concerns with pluggable components:
- `Fetcher` - HTTP/Browser content fetching
- `LinkExtractor` - Parse links from HTML
- `Paginator` - Handle pagination strategies

### Phase 3: Pagination Memory
Persistent pagination state in Source model for resumable crawls.

### Phase 4: Playwright JS Handling
Browser-based fetching for JavaScript-heavy sites:
- `HTTPFetcher` - Fast HTTP requests
- `PlaywrightFetcher` - Full browser rendering
- `HybridFetcher` - HTTP-first with browser fallback

### Phase 5: Extraction Quality
Hybrid content extraction combining multiple strategies:
- Trafilatura (primary)
- Newspaper3k (fallback)
- Quality scoring (EXCELLENT/GOOD/FAIR/POOR)

### Phase 6: State Machine
Robust article processing with state transitions:
```
collected → extracting → extracted → translating → translated → scoring → scored → completed
```

### Phase 7: LLM Hardening
Production-ready LLM integration:
- Versioned prompt templates
- Token counting and cost tracking
- Response caching
- Error handling and retries

### Phase 8: Observability
Full monitoring and debugging support:
- Structured JSON logging
- Metrics collection (counters, gauges, histograms)
- Health check endpoints
- Request tracing with correlation IDs

### Phase 9: Final Integration
All components validated working together:
- Cross-phase integration testing (30/30 tests passing)
- Package exports and API consistency
- Documentation updates

### Phase 10: Operator Console MVP
Complete REST API for operators:
- JWT authentication with SimpleJWT
- Sources CRUD with crawl triggers
- Runs API with filtering and aggregation
- Schedule editor with django-celery-beat
- Seeds manager with import/validate/promote
- Article viewer with 7-tab detail
- LLM settings and budget management
- HTMX templates for Operator Console UI

### Phase 11: API Gap Analysis Fixes
Security hardening and UX parity:
- SSRFGuard, URLNormalizer, SafeHTTPClient
- ErrorCode enum with 35+ codes
- Enhanced filters across all endpoints
- Discover-entrypoints, test-crawl endpoints

### Phase 12-13: Content Generation Pipeline
LLM-powered content creation:
- ContentOpportunity detection with gap analysis
- DraftGenerator with 8 content types
- Quality and originality scoring
- Async task pipeline with Celery

### Phase 14: Production API Improvements
Observability and performance:
- Prometheus metrics integration
- Request ID middleware
- Payload lazy loading
- Export job async flow

### Phase 15: Production Deployment
Docker and cloud-ready:
- Docker Compose with full stack
- OpenTelemetry tracing
- Nginx reverse proxy
- Jaeger, Prometheus, Grafana profiles

## 🌍 Regional Distribution

- **Southeast Asia**: 2 posts/week (50% crawler resources)
- **Central Asia**: 1 post/week
- **Africa**: 1 post/week
- **Latin/South America**: 1 post/week
- **MENA**: 1 post/week
- **Other Emerging Markets**: 1 post/week

## 📋 Current Status

**Phase**: 15 Complete + Phase 14.1 Audit  
**Last Updated**: 2025-12-24  
**Status**: Production Ready - Pre-Tagging Audit Complete

All core phases (2-15) complete with comprehensive API gap analysis fixes.

See [PROJECT_STATE.md](PROJECT_STATE.md) for detailed status.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Git

### Installation

```bash
# Clone repository (or navigate to project directory)
cd emcip

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your actual values

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Health Check Endpoints

Once running, the following endpoints are available:

```
GET /health/   - Full health check
GET /livez/    - Kubernetes liveness probe
GET /readyz/   - Kubernetes readiness probe
GET /metrics/  - Application metrics
GET /status/   - Application status summary
```

## 📚 Documentation

- **[claude.md](claude.md)** - Complete implementation guide for building with LLMs
- **[PROJECT_STATE.md](PROJECT_STATE.md)** - Current project state and progress
- **[BUILD_LOG.md](BUILD_LOG.md)** - Detailed session-by-session build history
- **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Testing documentation

## 🗂️ Project Structure

```
emcip/
├── config/                 # Django settings and configuration
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── celery.py
│   └── urls.py
├── apps/
│   ├── core/              # Observability, health checks, utilities
│   ├── sources/           # Source management and crawling
│   │   └── crawlers/      # Interface-based crawling system
│   │       ├── fetchers/  # HTTP, Playwright, Hybrid fetchers
│   │       ├── extractors/# Content extraction strategies
│   │       └── pagination/# Pagination strategies
│   ├── articles/          # Article storage, state machine, processing
│   ├── content/           # LLM integration, prompts, token tracking
│   ├── workflows/         # Editorial workflows and quotas
│   └── analytics/         # Metrics and monitoring
│   └── pipeline.py        # Unified pipeline runner
├── scripts/               # Utility and test scripts
├── docs/                  # Documentation
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── manage.py             # Django management script
```

## 🔧 Development Workflow

This project follows an incremental build approach:

1. Each feature is built in sessions (see [claude.md](claude.md))
2. Test after each session before proceeding
3. Update PROJECT_STATE.md after each successful test
4. Commit working code to git

## 🧪 Testing

```bash
# Run phase-specific tests
python scripts/test_integration.py      # All phases integration
python scripts/test_pagination_memory.py # Phase 3
python scripts/test_playwright.py       # Phase 4
python scripts/test_extraction.py       # Phase 5
python scripts/test_state_machine.py    # Phase 6
python scripts/test_llm_hardening.py    # Phase 7
python scripts/test_observability.py    # Phase 8

# Run Django tests
python manage.py test

# Run specific app tests
python manage.py test apps.articles

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.articles

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

## 📊 Key Features

- ✅ Automated web crawling with respect for robots.txt
- ✅ Multi-language support with translation
- ✅ AI-powered content scoring
- ✅ Source reputation learning
- ✅ Content opportunity identification
- ✅ Semi-automated content generation (75-85% complete)
- ✅ Editorial workflow management
- ✅ Regional quota management
- ✅ Analytics and monitoring

## 🤝 Contributing

This is an internal project. See [claude.md](claude.md) for implementation guidelines.

## 📄 License

Proprietary - Internal use only

## 🔗 Links

- [Technical Specification](docs/TECHNICAL_SPEC.md) (coming soon)
- [API Documentation](docs/API.md) (coming soon)
- [Deployment Guide](docs/DEPLOYMENT.md) (coming soon)

---

**Built with Claude Code following incremental development principles**
