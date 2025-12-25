# 06 Configuration and Environment

> **Purpose**: Complete documentation of all environment variables, configuration files, and settings with examples.

---

## 1. Environment Variables

### 1.1 Required Variables

| Variable | Description | Example | Required For |
|----------|-------------|---------|--------------|
| `SECRET_KEY` | Django secret key for cryptographic signing | `your-secret-key-here-at-least-50-chars` | All environments |
| `ANTHROPIC_API_KEY` | Claude API key from Anthropic | `sk-ant-api03-...` | LLM features |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://user:pass@host:5432/dbname` | Production |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` | Celery broker |

### 1.2 Optional Variables with Defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `False` | Enable Django debug mode |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | Settings module path |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allowed origins |

### 1.3 Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_NAME` | `emcip` | PostgreSQL database name |
| `DB_USER` | `emcip_user` | PostgreSQL username |
| `DB_PASSWORD` | *(required)* | PostgreSQL password |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |

**Alternative**: Use `DATABASE_URL` for full connection string.

### 1.4 Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Full Redis URL |
| `CELERY_BROKER_URL` | `$REDIS_URL` | Celery broker (defaults to REDIS_URL) |
| `CELERY_RESULT_BACKEND` | `$REDIS_URL` | Celery result backend |

### 1.5 LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required for LLM)* | Claude API key |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Claude model identifier |
| `LLM_MAX_TOKENS` | `4096` | Maximum output tokens |
| `LLM_TEMPERATURE` | `0.7` | Response randomness (0-1) |
| `LLM_DAILY_BUDGET` | `10.0` | Daily spending limit USD |

### 1.6 Translation Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_TRANSLATE_API_KEY` | *(optional)* | Google Translate API key |
| `TRANSLATION_ENABLED` | `True` | Enable translation pipeline |
| `TRANSLATION_TARGET_LANG` | `en` | Target language code |

### 1.7 Crawler Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CRAWLER_USER_AGENT` | `EMCIP-Bot/1.0` | Default user agent |
| `CRAWLER_DEFAULT_DELAY` | `2` | Seconds between requests |
| `CRAWLER_MAX_PAGES` | `3` | Default max pages per crawl |
| `CRAWLER_TIMEOUT` | `30` | Request timeout seconds |
| `AUTO_PROCESS_ARTICLES` | `False` | Auto-trigger processing pipeline |

### 1.8 Security Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000` | CSRF trusted origins |
| `SECURE_SSL_REDIRECT` | `False` | Force HTTPS redirect |
| `SECURE_HSTS_SECONDS` | `0` | HSTS header duration |
| `SESSION_COOKIE_SECURE` | `False` | Secure session cookies |

### 1.9 Observability Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(none)* | OpenTelemetry endpoint |
| `OTEL_SERVICE_NAME` | `emcip` | Service name for traces |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `verbose` | Log format style |

---

## 2. Settings Files

### 2.1 Base Settings (`config/settings/base.py`)

```python
# Core Django
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Installed Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'django_celery_beat',
    'django_filters',
    'corsheaders',
    # EMCIP apps
    'apps.core',
    'apps.sources',
    'apps.seeds',
    'apps.articles',
    'apps.content',
    'apps.workflows',
    'apps.analytics',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.RequestIDMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'burst': '30/minute',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.emcip_exception_handler',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_ROUTES = {
    'apps.sources.tasks.crawl_source': {'queue': 'crawl'},
    'apps.sources.tasks.validate_seed': {'queue': 'crawl'},
    'apps.seeds.tasks.*': {'queue': 'crawl'},
    'apps.articles.tasks.extract_*': {'queue': 'process'},
    'apps.articles.tasks.translate_*': {'queue': 'process'},
    'apps.articles.tasks.score_*': {'queue': 'process'},
    'apps.content.tasks.*': {'queue': 'content'},
}
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# LLM Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-20250514')
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '4096'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))

# Crawler Configuration
CRAWLER_USER_AGENT = os.getenv('CRAWLER_USER_AGENT', 'EMCIP-Bot/1.0 (Content Intelligence Platform)')
CRAWLER_DEFAULT_DELAY = int(os.getenv('CRAWLER_DEFAULT_DELAY', '2'))
CRAWLER_MAX_PAGES = int(os.getenv('CRAWLER_MAX_PAGES', '3'))
AUTO_PROCESS_ARTICLES = os.getenv('AUTO_PROCESS_ARTICLES', 'False').lower() == 'true'
```

### 2.2 Development Settings (`config/settings/development.py`)

```python
from .base import *

DEBUG = True

# SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Relaxed security
CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']

# Extended token lifetime for dev
SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] = timedelta(hours=24)

# Verbose logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

### 2.3 Production Settings (`config/settings/production.py`)

```python
from .base import *

DEBUG = False

# PostgreSQL for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'emcip'),
        'USER': os.getenv('DB_USER', 'emcip_user'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CORS
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
```

---

## 3. Celery Configuration

### 3.1 Celery App (`config/celery.py`)

```python
import os
from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('emcip')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Task routing
app.conf.task_routes = {
    'apps.sources.tasks.crawl_source': {'queue': 'crawl'},
    'apps.sources.tasks.*': {'queue': 'crawl'},
    'apps.seeds.tasks.*': {'queue': 'crawl'},
    'apps.articles.tasks.*': {'queue': 'process'},
    'apps.content.tasks.*': {'queue': 'content'},
}

# OpenTelemetry initialization
@worker_process_init.connect(weak=False)
def init_opentelemetry(**kwargs):
    """Initialize OpenTelemetry tracing for worker processes."""
    from apps.core.tracing import init_tracing
    init_tracing()
```

### 3.2 Worker Configuration

```bash
# Single worker (development)
celery -A config worker -l INFO

# Multi-queue workers (production)
celery -A config worker -Q crawl -c 4 -l INFO --hostname=crawl@%h
celery -A config worker -Q process -c 2 -l INFO --hostname=process@%h
celery -A config worker -Q content -c 2 -l INFO --hostname=content@%h
celery -A config worker -Q celery -c 1 -l INFO --hostname=default@%h
```

### 3.3 Beat Configuration

```bash
# Development (uses database scheduler)
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Production (with pidfile)
celery -A config beat -l INFO \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --pidfile=/var/run/celery/beat.pid
```

---

## 4. Docker Configuration

### 4.1 Docker Compose (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgres://emcip:${DB_PASSWORD}@db:5432/emcip
      - REDIS_URL=redis://redis:6379/0
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - db
      - redis

  celery-worker:
    build: .
    command: celery -A config worker -l INFO -Q crawl,process,content,celery
    volumes:
      - .:/app
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgres://emcip:${DB_PASSWORD}@db:5432/emcip
      - REDIS_URL=redis://redis:6379/0
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - .:/app
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgres://emcip:${DB_PASSWORD}@db:5432/emcip
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=emcip
      - POSTGRES_USER=emcip
      - POSTGRES_PASSWORD=${DB_PASSWORD}

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

### 4.2 Dockerfile

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

---

## 5. Sample Environment Files

### 5.1 Development (`.env.development`)

```bash
# Django
DEBUG=True
SECRET_KEY=dev-secret-key-not-for-production-use-only-for-local-dev
DJANGO_SETTINGS_MODULE=config.settings.development

# Database (SQLite used by default in development)

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM
ANTHROPIC_API_KEY=sk-ant-api03-your-dev-key-here
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# Crawler
CRAWLER_USER_AGENT=EMCIP-Dev-Bot/1.0
AUTO_PROCESS_ARTICLES=False
```

### 5.2 Production (`.env.production`)

```bash
# Django
DEBUG=False
SECRET_KEY=your-production-secret-key-minimum-50-characters-long
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=api.emcip.example.com,emcip.example.com

# Database
DB_NAME=emcip_prod
DB_USER=emcip_user
DB_PASSWORD=super-secure-database-password
DB_HOST=db.emcip.internal
DB_PORT=5432

# Redis
REDIS_URL=redis://redis.emcip.internal:6379/0

# LLM
ANTHROPIC_API_KEY=sk-ant-api03-production-key
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7
LLM_DAILY_BUDGET=50.0

# Crawler
CRAWLER_USER_AGENT=EMCIP-Bot/1.0 (https://emcip.example.com)
AUTO_PROCESS_ARTICLES=True

# Security
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://emcip.example.com,https://api.emcip.example.com
CORS_ALLOWED_ORIGINS=https://dashboard.emcip.example.com

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo.monitoring:4317
OTEL_SERVICE_NAME=emcip-api
LOG_LEVEL=INFO
```

---

## 6. Configuration Validation

### 6.1 Startup Checks

```python
# Run during Django startup
python manage.py check

# Verify migrations
python manage.py migrate --check

# Test database connection
python manage.py dbshell

# Test Redis connection
python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.ping())"

# Test Celery broker
celery -A config inspect ping
```

### 6.2 Health Check Endpoints

```python
# Recommended health check implementation
# apps/core/views.py

class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        checks = {
            'database': self._check_database(),
            'redis': self._check_redis(),
            'celery': self._check_celery(),
        }
        
        healthy = all(c['status'] == 'ok' for c in checks.values())
        status_code = 200 if healthy else 503
        
        return Response({
            'status': 'healthy' if healthy else 'unhealthy',
            'checks': checks,
        }, status=status_code)
```

---

## 7. Secrets Management

### 7.1 Development

- Store secrets in `.env` file (gitignored)
- Use python-dotenv to load automatically

### 7.2 Production Recommendations

| Method | Provider | Use Case |
|--------|----------|----------|
| Environment variables | All | Container deployments |
| AWS Secrets Manager | AWS | ECS, EKS deployments |
| HashiCorp Vault | Multi-cloud | Enterprise setups |
| Azure Key Vault | Azure | AKS deployments |
| Google Secret Manager | GCP | GKE deployments |

### 7.3 Secret Rotation

| Secret | Rotation Frequency | Procedure |
|--------|-------------------|-----------|
| `SECRET_KEY` | Annually | Invalidates sessions |
| `ANTHROPIC_API_KEY` | On compromise | Update env, restart |
| `DB_PASSWORD` | Quarterly | Coordinate with DBA |

---

## 8. Feature Flags (Phase 16)

### 8.1 Discovery Pipeline Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCOVERY_PIPELINE_ENABLED` | `False` | Enable seed discovery pipeline |
| `CAPTURE_STORAGE_ENABLED` | `True` | Store raw HTTP captures |
| `CAPTURE_TTL_DAYS` | `30` | Days to retain capture files |
| `MAX_CAPTURES_PER_RUN` | `100` | Max captures per discovery run |
| `SERP_API_KEY` | *(optional)* | Search API key for connectors |
| `DISCOVERY_RATE_LIMIT` | `1.0` | Seconds between discovery requests |
| `ALLOW_INSECURE_TLS` | `False` | Allow self-signed certificates (dev only) |

### 8.2 Capture Storage Settings

```python
# config/settings/base.py (Phase 16 additions)

# Discovery capture storage
CAPTURE_STORAGE_DIR = os.path.join(MEDIA_ROOT, 'captures')
CAPTURE_INLINE_THRESHOLD = 50 * 1024  # 50KB - store inline if smaller
CAPTURE_MAX_SIZE = 500 * 1024         # 500KB - truncate if larger
CAPTURE_COMPRESSION_LEVEL = 6         # gzip level 1-9

# Discovery pipeline
DISCOVERY_DEFAULT_MAX_RESULTS = 50    # Default results per query
DISCOVERY_CONNECTOR_TIMEOUT = 30      # Seconds per connector request
DISCOVERY_CLASSIFIER_CONFIDENCE = 0.6 # Min confidence for seed creation
```

### 8.3 Scoring Weights

```python
# Seed scoring weights (Phase 16)
SEED_SCORING_WEIGHTS = {
    'relevance': 0.35,     # Topical relevance weight
    'utility': 0.25,       # Scrape utility weight
    'freshness': 0.20,     # Content freshness weight
    'authority': 0.20,     # Source authority weight
}
```

### 8.4 Environment Examples

**Development with Discovery Enabled**:
```bash
# .env.development additions
DISCOVERY_PIPELINE_ENABLED=True
CAPTURE_STORAGE_ENABLED=True
ALLOW_INSECURE_TLS=True
DISCOVERY_RATE_LIMIT=0.5
MAX_CAPTURES_PER_RUN=20
```

**Production with Full Discovery**:
```bash
# .env.production additions
DISCOVERY_PIPELINE_ENABLED=True
CAPTURE_STORAGE_ENABLED=True
CAPTURE_TTL_DAYS=30
MAX_CAPTURES_PER_RUN=100
SERP_API_KEY=your-serp-api-key
DISCOVERY_RATE_LIMIT=1.0
ALLOW_INSECURE_TLS=False
```

---

## 9. Management Commands

### 9.1 Discovery Commands (Phase 16)

```bash
# Run discovery with CLI fallback (no Celery required)
python manage.py run_discovery \
    --theme "renewable energy" \
    --geography US GB DE \
    --entity-types news blog \
    --keywords solar wind hydro \
    --max-results 50 \
    --dry-run

# With capture storage disabled
python manage.py run_discovery \
    --theme "fintech startups" \
    --geography US \
    --skip-capture

# Generate queries only (no fetching)
python manage.py run_discovery \
    --theme "AI healthcare" \
    --generate-only
```

### 9.2 Capture Maintenance

```bash
# Future: Clean up old captures
python manage.py cleanup_captures --older-than 30

# Future: Verify capture file integrity
python manage.py verify_captures --fix-missing
```

---

**Document Version**: 2.0.0  
**Last Updated**: Session 30 (Phase 16)  
**Maintainer**: EMCIP Development Team
