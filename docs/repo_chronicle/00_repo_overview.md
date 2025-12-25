# 00 Repository Overview

> **Purpose**: Provide high-level understanding of EMCIP's purpose, value proposition, and core capabilities.

---

## 1. Executive Summary

**EMCIP (Emerging Markets Content Intelligence Platform)** is an automated content intelligence system that:

1. **Aggregates** news and information from emerging market sources globally
2. **Processes** content through extraction, translation, and quality scoring
3. **Identifies** content opportunities using AI-powered analysis
4. **Synthesizes** original content drafts from aggregated intelligence

The platform serves content strategists, analysts, and publishers who need comprehensive emerging markets coverage without manual research overhead.

---

## 2. Business Problem Solved

### 2.1 The Challenge

Emerging markets intelligence is fragmented across:
- Hundreds of regional news sources
- Multiple languages (Arabic, Chinese, Spanish, Portuguese, etc.)
- Varying content quality and reliability
- Rapidly evolving news cycles

Manual monitoring is:
- Time-intensive (8-12 hours/day for comprehensive coverage)
- Error-prone (human fatigue leads to missed stories)
- Inconsistent (coverage gaps in unfamiliar regions)
- Not scalable (linear effort vs. exponential source growth)

### 2.2 EMCIP's Solution

Automated pipeline that:
- **Crawls** 100+ sources on configurable schedules
- **Extracts** clean text from messy HTML
- **Translates** non-English content to English
- **Scores** articles on relevance, quality, timeliness
- **Identifies** synthesis opportunities via LLM analysis
- **Generates** draft content for human review

---

## 3. Core Capabilities

### 3.1 Source Management

| Capability | Description |
|------------|-------------|
| Multi-region sources | Southeast Asia, Central Asia, MENA, Africa, Latin America |
| Crawler configuration | Per-source settings for pagination, rate limits, selectors |
| Health monitoring | Track crawl success rates, error patterns, content quality |
| Automatic scheduling | Celery Beat schedules crawls based on source update frequency |

### 3.2 Content Processing Pipeline

```
[Crawl] → [Seed] → [Article] → [Extract] → [Translate] → [Score] → [Complete]
```

Each stage is:
- **Idempotent**: Can retry without side effects
- **Observable**: Status tracked in database
- **Async**: Celery tasks for background processing
- **Recoverable**: Failed items can be reprocessed

### 3.3 Intelligence Generation

| Feature | Description |
|---------|-------------|
| Opportunity Detection | LLM identifies trending topics, coverage gaps, follow-up stories |
| Draft Synthesis | Generate blog posts, newsletters, executive summaries |
| Quality Scoring | AI-assessed originality, coherence, factual grounding |
| Template Support | Customizable prompts for different content types |

---

## 4. Target Users

### 4.1 Primary Users

| Role | Use Case |
|------|----------|
| **Content Strategist** | Identify content opportunities, prioritize topics |
| **Analyst** | Research emerging market trends, generate reports |
| **Editor** | Review and publish AI-generated drafts |
| **Operations** | Monitor system health, manage sources |

### 4.2 Integration Points

- **API Consumers**: External applications consuming processed content
- **Publishers**: CMS integrations for draft publishing
- **Analytics**: BI tools consuming metrics and trends

---

## 5. Key Metrics

### 5.1 Operational Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Sources Active | 100+ | Number of configured, crawlable sources |
| Daily Articles | 500+ | New articles collected per day |
| Processing Rate | <5 min | Time from crawl to completion |
| Translation Coverage | 15+ languages | Supported source languages |

### 5.2 Quality Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| High-Quality Rate | 30%+ | Articles scoring 70+ |
| Duplicate Rate | <5% | Percentage of duplicate articles |
| AI Detection Rate | <10% | Articles flagged as AI-generated |
| Draft Acceptance | 60%+ | Drafts published without major edits |

---

## 6. Technology Stack

### 6.1 Core Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Web Framework** | Django 5.0+ | Application structure, ORM, admin |
| **API Layer** | Django REST Framework | RESTful API endpoints |
| **Task Queue** | Celery 5.3+ | Async processing, scheduling |
| **Message Broker** | Redis 7+ | Task queue backend, caching |
| **Database** | PostgreSQL 15+ | Primary data storage |
| **LLM** | Claude (Anthropic) | Content analysis, generation |

### 6.2 Supporting Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Content Extraction** | Trafilatura, Newspaper3k | HTML to text conversion |
| **Translation** | Google Translate API | Non-English content |
| **Language Detection** | langdetect | Source language identification |
| **Observability** | OpenTelemetry, Prometheus | Tracing, metrics |
| **Authentication** | SimpleJWT | API token management |

---

## 7. Deployment Model

### 7.1 Production Stack

```
┌─────────────────────────────────────────────────────────┐
│                      Load Balancer                      │
└───────────────────────────┬─────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
    ┌───────┴───────┐               ┌───────┴───────┐
    │   Web Server  │               │   Web Server  │
    │   (Gunicorn)  │               │   (Gunicorn)  │
    └───────┬───────┘               └───────┬───────┘
            │                               │
            └───────────────┬───────────────┘
                            │
    ┌───────────────────────┴───────────────────────┐
    │                                               │
    │              Celery Workers                   │
    │   ┌─────────┬─────────┬─────────┬─────────┐  │
    │   │  crawl  │ process │ content │ default │  │
    │   │   (4)   │   (2)   │   (2)   │   (1)   │  │
    │   └─────────┴─────────┴─────────┴─────────┘  │
    │                                               │
    └───────────────────────┬───────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
    ┌───────┴───────┐               ┌───────┴───────┐
    │     Redis     │               │  PostgreSQL   │
    │   (Broker)    │               │  (Database)   │
    └───────────────┘               └───────────────┘
```

### 7.2 Scaling Considerations

| Component | Scaling Strategy |
|-----------|------------------|
| Web servers | Horizontal (add instances) |
| Celery workers | Horizontal per queue |
| Redis | Vertical (memory), Redis Cluster for HA |
| PostgreSQL | Read replicas, connection pooling |

---

## 8. Project History

### 8.1 Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1-3 | Project setup, models, admin | ✅ Complete |
| 4-6 | Crawlers, extraction, translation | ✅ Complete |
| 7-9 | LLM integration, scoring, content | ✅ Complete |
| 10-11 | Multi-source crawl, seeds, orchestration | ✅ Complete |
| 12-13 | Opportunity detection, draft synthesis | ✅ Complete |
| 14+ | Export, analytics, production hardening | 🔄 Active |

### 8.2 Current State

As of Session 26:
- **Core pipeline**: Fully operational
- **API coverage**: Complete CRUD for all entities
- **LLM integration**: Claude Sonnet 4 with fallbacks
- **Production readiness**: Security hardened, rate limited, monitored

---

## 9. Documentation Map

| Document | Purpose |
|----------|---------|
| [000_llm_agent_instruction.md](000_llm_agent_instruction.md) | LLM agent operating guidelines |
| [01_system_architecture.md](01_system_architecture.md) | Technical architecture deep-dive |
| [02_directory_and_module_map.md](02_directory_and_module_map.md) | File/folder structure explanation |
| [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) | Key functions and classes |
| [04_data_models_and_state.md](04_data_models_and_state.md) | Database schema and state machines |
| [05_execution_and_runtime_flow.md](05_execution_and_runtime_flow.md) | Startup and request handling |
| [06_configuration_and_environment.md](06_configuration_and_environment.md) | Settings and environment variables |
| [07_rebuild_from_scratch.md](07_rebuild_from_scratch.md) | Complete reconstruction guide |
| [08_known_tradeoffs_and_future_extensions.md](08_known_tradeoffs_and_future_extensions.md) | Technical debt and roadmap |

---

## 10. Quick Start Commands

### 10.1 Development Setup

```bash
# Clone and setup
git clone <repository>
cd emcip
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### 10.2 Run Celery Workers

```bash
# Start Redis (required)
redis-server

# Start Celery worker
celery -A config worker -l INFO

# Start Celery beat (scheduler)
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 10.3 Run Tests

```bash
pytest
pytest --cov=apps --cov-report=html
```

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
