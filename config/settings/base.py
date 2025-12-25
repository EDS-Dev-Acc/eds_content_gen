"""
Django settings for EMCIP project.
Base settings shared across all environments.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_celery_beat',

    # EMCIP apps
    'apps.core',
    'apps.sources',
    'apps.articles',
    'apps.content',
    'apps.workflows',
    'apps.analytics',
    'apps.seeds',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom middleware
    'apps.core.middleware.RequestIDMiddleware',  # Request ID tracing
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
# Use SQLite for development if no PostgreSQL configured
if os.getenv('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }
else:
    # SQLite fallback for initial development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 540  # 9 minutes
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True

# Additional Celery settings for production reliability
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_RESULT_EXTENDED = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Prevent worker from grabbing too many tasks

# Celery Beat (scheduled tasks) - using django-celery-beat DB scheduler
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
# Note: Static schedules moved to DB via django-celery-beat admin
# Legacy static schedule (for backward compatibility):
CELERY_BEAT_SCHEDULE = {
    'crawl-all-sources-hourly': {
        'task': 'apps.sources.tasks.crawl_all_active_sources',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-old-exports-daily': {
        'task': 'apps.articles.tasks.cleanup_old_exports',
        'schedule': 86400.0,  # Every 24 hours
        # Uses EXPORT_TTL_COMPLETED_DAYS and EXPORT_TTL_FAILED_DAYS from settings
    },
    'cleanup-old-captures-daily': {
        'task': 'apps.seeds.discovery.tasks.cleanup_old_captures',
        'schedule': 86400.0,  # Every 24 hours
        'kwargs': {'days': 30},
    },
}

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'db': 0,
        }
    }
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Custom exception handler for standardized error responses
    'EXCEPTION_HANDLER': 'apps.core.exceptions.emcip_exception_handler',
}

# Simple JWT Configuration
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

# LLM Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_API_KEY_FALLBACK = os.getenv('ANTHROPIC_API_KEY_FALLBACK', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-20250514')
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '4000'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))

# Translation Configuration
GOOGLE_TRANSLATE_API_KEY = os.getenv('GOOGLE_TRANSLATE_API_KEY', '')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
TRANSLATION_CACHE_TTL = int(os.getenv('TRANSLATION_CACHE_TTL', '2592000'))  # 30 days
DEFAULT_TARGET_LANGUAGE = os.getenv('DEFAULT_TARGET_LANGUAGE', 'en')
ENABLE_TRANSLATION = os.getenv('ENABLE_TRANSLATION', 'False').lower() == 'true'

# Crawler Configuration
CRAWLER_USER_AGENT = os.getenv(
    'CRAWLER_USER_AGENT',
    'EMCIP-Bot/1.0 (Content Intelligence Platform)'
)
CRAWLER_DELAY = int(os.getenv('CRAWLER_DELAY', '2'))
CRAWLER_MAX_PAGES = int(os.getenv('CRAWLER_MAX_PAGES', '3'))
MAX_ARTICLES_PER_CRAWL = int(os.getenv('MAX_ARTICLES_PER_CRAWL', '50'))
AUTO_PROCESS_ARTICLES = os.getenv('AUTO_PROCESS_ARTICLES', 'True').lower() == 'true'

# Search API Configuration
SERPAPI_KEY = os.getenv('SERPAPI_KEY', '')
GOOGLE_CUSTOM_SEARCH_KEY = os.getenv('GOOGLE_CUSTOM_SEARCH_KEY', '')
GOOGLE_CUSTOM_SEARCH_CX = os.getenv('GOOGLE_CUSTOM_SEARCH_CX', '')
SEARCH_QUERIES_PER_DAY = int(os.getenv('SEARCH_QUERIES_PER_DAY', '10'))

# AWS S3 Configuration (for production)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', '')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@emcip.com')

# Logging
# Note: Request ID filter added in middleware. For logging config we use a
# simpler approach that doesn't require the filter module at startup time.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 5,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# =============================================================================
# Feature Flags
# =============================================================================

# Phase 16: Discovery Pipeline
# Enable automated seed discovery pipeline (requires Redis/Celery)
DISCOVERY_PIPELINE_ENABLED = os.getenv('DISCOVERY_PIPELINE_ENABLED', 'false').lower() == 'true'

# Enable capture storage for discovery (stores raw HTTP responses)
CAPTURE_STORAGE_ENABLED = os.getenv('CAPTURE_STORAGE_ENABLED', 'true').lower() == 'true'

# Discovery capture TTL in days (for cleanup task)
CAPTURE_TTL_DAYS = int(os.getenv('CAPTURE_TTL_DAYS', '7'))

# Maximum captures to keep per discovery run
MAX_CAPTURES_PER_RUN = int(os.getenv('MAX_CAPTURES_PER_RUN', '1000'))

# SERP API key for web search discovery (optional)
SERP_API_KEY = os.getenv('SERP_API_KEY', '')

# Discovery rate limit (requests per minute per domain)
DISCOVERY_RATE_LIMIT = int(os.getenv('DISCOVERY_RATE_LIMIT', '10'))

# Allow per-source TLS verification override (security consideration)
ALLOW_INSECURE_TLS = os.getenv('ALLOW_INSECURE_TLS', 'false').lower() == 'true'


# =============================================================================
# Export Configuration (Phase 18)
# =============================================================================

# TTL for completed exports (days before cleanup)
EXPORT_TTL_COMPLETED_DAYS = int(os.getenv('EXPORT_TTL_COMPLETED_DAYS', '30'))

# TTL for failed exports (days before cleanup)
EXPORT_TTL_FAILED_DAYS = int(os.getenv('EXPORT_TTL_FAILED_DAYS', '7'))


# =============================================================================
# Probe Caps Configuration (Phase 18)
# =============================================================================

# Maximum links analyzed per page in discover/test-crawl
PROBE_MAX_LINKS_PER_PAGE = int(os.getenv('PROBE_MAX_LINKS_PER_PAGE', '100'))

# Maximum total pages to fetch during test-crawl
PROBE_MAX_PAGES = int(os.getenv('PROBE_MAX_PAGES', '20'))

# Maximum articles to return from test-crawl
PROBE_MAX_ARTICLES = int(os.getenv('PROBE_MAX_ARTICLES', '10'))

# Maximum total entrypoint candidates during discovery
PROBE_MAX_TOTAL_ENTRYPOINTS = int(os.getenv('PROBE_MAX_TOTAL_ENTRYPOINTS', '50'))

# Maximum entrypoints returned in discovery response
PROBE_MAX_RESULT_ENTRYPOINTS = int(os.getenv('PROBE_MAX_RESULT_ENTRYPOINTS', '20'))

# Maximum content size per page (bytes) - truncate above this
PROBE_MAX_CONTENT_SIZE = int(os.getenv('PROBE_MAX_CONTENT_SIZE', str(2 * 1024 * 1024)))  # 2MB

# Time budget per page analysis (seconds)
PROBE_PAGE_TIMEOUT = int(os.getenv('PROBE_PAGE_TIMEOUT', '10'))


# =============================================================================
# OpenTelemetry Tracing
# =============================================================================

# Enable OpenTelemetry tracing (set to True in production with collector)
OTEL_ENABLED = os.getenv('OTEL_ENABLED', 'false').lower() == 'true'

# Service name for tracing
OTEL_SERVICE_NAME = os.getenv('OTEL_SERVICE_NAME', 'emcip')

# OTLP exporter endpoint (e.g., "http://localhost:4317" for gRPC)
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', None)

# Enable console span export for debugging
OTEL_CONSOLE_EXPORT = os.getenv('OTEL_CONSOLE_EXPORT', 'false').lower() == 'true'

# Application version for tracing
VERSION = os.getenv('APP_VERSION', '1.0.0')

