# 07 Rebuild From Scratch

> **Purpose**: Step-by-step guide to reconstruct the entire system using only this documentation.

---

## 1. Prerequisites

### 1.1 Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Runtime environment |
| PostgreSQL | 15+ | Production database |
| Redis | 7+ | Message broker & cache |
| Git | 2.40+ | Version control |

### 1.2 Optional Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 24+ | Containerization |
| Docker Compose | 2.20+ | Multi-container orchestration |

### 1.3 API Keys Required

| Service | Purpose | Obtain From |
|---------|---------|-------------|
| Anthropic Claude | LLM content generation | console.anthropic.com |
| Google Translate | Article translation | cloud.google.com |

---

## 2. Project Initialization

### 2.1 Create Project Structure

```bash
# Create project directory
mkdir emcip
cd emcip

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Unix/Mac)
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 2.2 Install Core Dependencies

```bash
pip install django==5.0
pip install djangorestframework==3.14.0
pip install djangorestframework-simplejwt==5.3.0
pip install django-filter==23.5
pip install django-cors-headers==4.3.1
pip install celery==5.3.4
pip install redis==5.0.1
pip install django-celery-beat==2.5.0
pip install psycopg2-binary==2.9.9
pip install requests==2.31.0
pip install langdetect==1.0.9
pip install newspaper3k==0.2.8
pip install trafilatura==1.6.2
pip install python-dotenv==1.0.0
pip install gunicorn==21.2.0
```

### 2.3 Create Django Project

```bash
django-admin startproject config .
```

### 2.4 Create Application Structure

```bash
mkdir apps
touch apps/__init__.py

# Create each Django app
cd apps
django-admin startapp core
django-admin startapp sources
django-admin startapp seeds
django-admin startapp articles
django-admin startapp content
django-admin startapp workflows
django-admin startapp analytics
cd ..
```

---

## 3. Configuration Setup

### 3.1 Create Settings Structure

```bash
mkdir config/settings
touch config/settings/__init__.py
touch config/settings/base.py
touch config/settings/development.py
touch config/settings/production.py
```

### 3.2 Base Settings (`config/settings/base.py`)

```python
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

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

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.emcip_exception_handler',
}

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# LLM
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-20250514')
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '4096'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))

# Crawler
CRAWLER_USER_AGENT = 'EMCIP-Bot/1.0'
AUTO_PROCESS_ARTICLES = os.getenv('AUTO_PROCESS_ARTICLES', 'False').lower() == 'true'
```

### 3.3 Create Celery App (`config/celery.py`)

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('emcip')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.task_routes = {
    'apps.sources.tasks.*': {'queue': 'crawl'},
    'apps.seeds.tasks.*': {'queue': 'crawl'},
    'apps.articles.tasks.*': {'queue': 'process'},
    'apps.content.tasks.*': {'queue': 'content'},
}
```

### 3.4 Update Config Init (`config/__init__.py`)

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

---

## 4. Model Implementation

### 4.1 Core Models (`apps/core/models.py`)

```python
import uuid
from django.db import models
from django.contrib.auth.models import User

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class OperatorProfile(BaseModel):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('operator', 'Operator'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    preferences = models.JSONField(default=dict, blank=True)
```

### 4.2 Sources Models (`apps/sources/models.py`)

See [04_data_models_and_state.md](04_data_models_and_state.md) for complete Source and CrawlJob model definitions.

### 4.3 Articles Models (`apps/articles/models.py`)

See [04_data_models_and_state.md](04_data_models_and_state.md) for complete Article model definition.

### 4.4 Seeds Models (`apps/seeds/models.py`)

See [04_data_models_and_state.md](04_data_models_and_state.md) for complete Seed model definition.

### 4.5 Content Models (`apps/content/models.py`)

See [04_data_models_and_state.md](04_data_models_and_state.md) for complete ContentOpportunity and ContentDraft model definitions.

---

## 5. Core Utilities Implementation

### 5.1 Request ID Middleware (`apps/core/middleware.py`)

```python
import uuid

class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request.request_id = request_id
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response
```

### 5.2 Exception Handler (`apps/core/exceptions.py`)

```python
from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        request = context.get('request')
        request_id = getattr(request, 'request_id', None)
        
        response.data['request_id'] = request_id
        
        if hasattr(exc, 'code'):
            response.data['code'] = exc.code
    
    return response
```

### 5.3 SSRF Protection (`apps/core/security.py`)

```python
import ipaddress
from urllib.parse import urlparse
import socket
import requests

class HTTPFetcher:
    BLOCKED_NETWORKS = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),
        ipaddress.ip_network('169.254.0.0/16'),
    ]
    
    @classmethod
    def is_blocked_ip(cls, ip_str):
        try:
            ip = ipaddress.ip_address(ip_str)
            return any(ip in network for network in cls.BLOCKED_NETWORKS)
        except ValueError:
            return True
    
    @classmethod
    def fetch(cls, url, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Invalid scheme: {parsed.scheme}")
        
        try:
            ip = socket.gethostbyname(parsed.hostname)
            if cls.is_blocked_ip(ip):
                raise ValueError(f"Blocked IP: {ip}")
        except socket.gaierror:
            raise ValueError(f"Cannot resolve: {parsed.hostname}")
        
        return requests.get(url, **kwargs)
```

---

## 6. Service Layer Implementation

### 6.1 Crawler Base (`apps/sources/crawlers/base.py`)

See [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) for BaseCrawler implementation.

### 6.2 Article Services (`apps/articles/services.py`)

See [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) for ArticleExtractor, ArticleTranslator, ArticleScorer implementations.

### 6.3 LLM Client (`apps/content/llm.py`)

See [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) for ClaudeClient implementation.

### 6.4 Opportunity Finder (`apps/content/opportunity.py`)

See [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) for OpportunityFinder implementation.

### 6.5 Draft Generator (`apps/content/synthesis.py`)

See [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) for DraftGenerator implementation.

---

## 7. Celery Tasks Implementation

### 7.1 Source Tasks (`apps/sources/tasks.py`)

```python
from celery import shared_task
from django.utils import timezone

@shared_task(bind=True, max_retries=3)
def crawl_source(self, source_id, crawl_job_id=None, parent_job_id=None, config_overrides=None):
    from apps.sources.models import Source, CrawlJob
    from apps.sources.crawlers import get_crawler
    
    try:
        source = Source.objects.get(id=source_id)
        crawl_job = CrawlJob.objects.get(id=crawl_job_id) if crawl_job_id else None
        
        if not crawl_job:
            crawl_job = CrawlJob.objects.create(
                source=source,
                status='pending',
                task_id=self.request.id,
            )
        
        crawl_job.status = 'running'
        crawl_job.started_at = timezone.now()
        crawl_job.save()
        
        crawler = get_crawler(source, config=config_overrides or {})
        results = crawler.crawl()
        
        crawl_job.status = 'completed'
        crawl_job.completed_at = timezone.now()
        crawl_job.total_found = results.get('total_found', 0)
        crawl_job.new_articles = results.get('new_articles', 0)
        crawl_job.save()
        
        return {'success': True, 'results': results}
        
    except Exception as exc:
        if crawl_job:
            crawl_job.status = 'failed'
            crawl_job.error_message = str(exc)
            crawl_job.save()
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### 7.2 Article Tasks (`apps/articles/tasks.py`)

```python
from celery import shared_task

@shared_task(bind=True, max_retries=2)
def process_article_pipeline(self, article_id, translate=True, score=True):
    from apps.articles.models import Article
    from apps.articles.services import ArticleProcessor
    
    try:
        article = ArticleProcessor().process(article_id, translate=translate, score=score)
        return {'article_id': str(article.id), 'status': article.processing_status}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
```

### 7.3 Content Tasks (`apps/content/tasks.py`)

```python
from celery import shared_task

@shared_task(bind=True, max_retries=2, soft_time_limit=300)
def generate_opportunities(self, limit=10, topic=None, region=None, save=False):
    from apps.content.opportunity import OpportunityFinder
    
    result = OpportunityFinder().generate(
        limit=limit,
        topic=topic,
        region=region,
        save=save,
    )
    return result
```

---

## 8. API Implementation

### 8.1 URL Configuration (`config/urls.py`)

```python
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view()),
    path('api/auth/token/refresh/', TokenRefreshView.as_view()),
    path('api/sources/', include('apps.sources.urls')),
    path('api/seeds/', include('apps.seeds.urls')),
    path('api/articles/', include('apps.articles.urls')),
    path('api/content/', include('apps.content.urls')),
]
```

### 8.2 ViewSets

Create ViewSets in each app's `views.py` following DRF patterns. See [03_core_logic_deep_dive.md](03_core_logic_deep_dive.md) for API structure.

---

## 9. Database Setup

### 9.1 Run Migrations

```bash
# Create migrations
python manage.py makemigrations core
python manage.py makemigrations sources
python manage.py makemigrations seeds
python manage.py makemigrations articles
python manage.py makemigrations content

# Apply migrations
python manage.py migrate
```

### 9.2 Create Superuser

```bash
python manage.py createsuperuser
```

---

## 10. Verification Checklist

### 10.1 Django Checks

```bash
python manage.py check
python manage.py showmigrations
python manage.py runserver
```

### 10.2 Celery Checks

```bash
# Start Redis
redis-server

# Start worker
celery -A config worker -l INFO

# Start beat
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 10.3 API Checks

```bash
# Get token
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# List sources
curl http://localhost:8000/api/sources/ \
  -H "Authorization: Bearer <token>"
```

---

## 11. Production Deployment

### 11.1 Environment Setup

```bash
# Set production settings
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY="your-production-secret-key"
export DATABASE_URL="postgres://user:pass@host:5432/dbname"
export REDIS_URL="redis://redis-host:6379/0"
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 11.2 Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 11.3 Run with Gunicorn

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### 11.4 Docker Deployment

```bash
docker-compose up -d
```

---

## 12. Post-Deployment Configuration

### 12.1 Create Initial Sources

```python
# Django shell
from apps.sources.models import Source

Source.objects.create(
    name="Example News",
    domain="example.com",
    url="https://example.com/news",
    source_type="news",
    region="global",
    crawler_type="requests",
    is_active=True,
)
```

### 12.2 Configure Periodic Tasks

Access Django Admin at `/admin/` and configure:
- Periodic tasks in `django_celery_beat`
- Crawl schedules for sources

### 12.3 Test End-to-End

1. Create a source
2. Trigger crawl via API
3. Verify articles created
4. Run processing pipeline
5. Generate content opportunities
6. Create draft

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
