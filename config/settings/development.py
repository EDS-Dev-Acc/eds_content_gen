"""
Development settings for EMCIP project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']

# Development-specific apps
# INSTALLED_APPS += [
#     'django_extensions',  # Optional: adds useful management commands (install separately if needed)
# ]

# Development email backend (console)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable HTTPS redirect in development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Show more detailed error pages
DEBUG_PROPAGATE_EXCEPTIONS = True

# Development logging - more verbose, no file rotation (Windows file locking issue)
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['apps']['level'] = 'DEBUG'

# Disable file logging in development to avoid Windows file rotation issues
LOGGING['handlers']['file'] = {
    'class': 'logging.FileHandler',
    'filename': BASE_DIR / 'logs' / 'django.log',
    'formatter': 'verbose',
    'mode': 'a',
}
