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
- **Crawling**: Scrapy, Playwright, Selenium

## 🌍 Regional Distribution

- **Southeast Asia**: 2 posts/week (50% crawler resources)
- **Central Asia**: 1 post/week
- **Africa**: 1 post/week
- **Latin/South America**: 1 post/week
- **MENA**: 1 post/week
- **Other Emerging Markets**: 1 post/week

## 📋 Current Status

**Phase**: 0 - Preparation
**Last Updated**: 2024-12-20
**Status**: Initial setup

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

# Install dependencies (after Session 1)
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your actual values

# Run migrations (after Session 2)
python manage.py migrate

# Create superuser (after Session 3)
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## 📚 Documentation

- **[claude.md](claude.md)** - Complete implementation guide for building with LLMs
- **[PROJECT_STATE.md](PROJECT_STATE.md)** - Current project state and progress
- **[BUILD_LOG.md](BUILD_LOG.md)** - Detailed session-by-session build history
- **docs/** - Additional documentation (coming soon)

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
│   ├── core/              # Shared utilities and base models
│   ├── sources/           # Source management and crawling
│   ├── articles/          # Article storage and processing
│   ├── content/           # Content generation and LLM integration
│   ├── workflows/         # Editorial workflows and quotas
│   └── analytics/         # Metrics and monitoring
├── scripts/               # Utility scripts
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
