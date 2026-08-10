"""
Medical Search Platform - Django Settings
Copyright (c) 2025 DRCI - CHU Clermont-Ferrand
All rights reserved.

Author: FIANKO Kossi Jean-Jacques Daniel
License: MIT License (see LICENSE file)
"""

import os
import warnings
from importlib.util import find_spec
from pathlib import Path
from dotenv import load_dotenv

HAS_WHITENOISE = find_spec('whitenoise') is not None

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'

# SECRET_KEY: require a real key in production
_default_key = 'dev-insecure-key'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', _default_key)
if not DEBUG and SECRET_KEY == _default_key:
    raise RuntimeError(
        'DJANGO_SECRET_KEY must be set in production. '
        'Generate one with: python -c "from django.core.secret import get_random_secret_key; print(get_random_secret_key())"'
    )

# ALLOWED_HOSTS: refuse wildcard in production
ALLOWED_HOSTS = [h for h in os.getenv('ALLOWED_HOSTS', '*').split(',') if h]
if not DEBUG and ALLOWED_HOSTS == ['*']:
    warnings.warn(
        'ALLOWED_HOSTS is set to ["*"] in production. '
        'Set a specific hostname via the ALLOWED_HOSTS environment variable.',
        RuntimeWarning,
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'search',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Security middleware
    'config.middleware.SecurityHeadersMiddleware',
    'config.middleware.RateLimitMiddleware',
    'config.middleware.LoggingMiddleware',
    'config.middleware.ProxyCompatibilityMiddleware',
]

if HAS_WHITENOISE:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
else:
    warnings.warn(
        'Whitenoise is not installed; static files will be served by Django. '
        'Install whitenoise for production deployments.',
        RuntimeWarning,
    )

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
                'search.context_processors.cache_state',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'

if HAS_WHITENOISE:
    # CompressedStaticFilesStorage compresses files but does NOT require a manifest,
    # avoiding "Missing staticfiles manifest entry" errors in Docker/Cloud Run.
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CACHE_THRESHOLD = int(os.getenv('CACHE_THRESHOLD', '50'))

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser']
}

# ============================================================================
# SECURITY CONFIGURATION (from config/security.py)
# ============================================================================

# HTTPS/SSL Configuration
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'false').lower() == 'true'
SESSION_COOKIE_SECURE = os.getenv('SECURE_SSL_REDIRECT', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = os.getenv('SECURE_SSL_REDIRECT', 'false').lower() == 'true'

# CSRF Configuration
CSRF_TRUSTED_ORIGINS = [h for h in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000').split(',') if h]

# Rate limiting configuration (no authentication needed)
RATELIMIT_ENABLE = os.getenv('RATELIMIT_ENABLE', 'true').lower() == 'true'
RATELIMIT_RATE = os.getenv('RATELIMIT_RATE', '200/h')  # 200 requests per hour
RATELIMIT_INTERVAL = int(os.getenv('RATELIMIT_INTERVAL', '3600'))  # 1 hour
RATELIMIT_BURST = int(os.getenv('RATELIMIT_BURST', '4'))  # 4 requests
RATELIMIT_BURST_WINDOW = int(os.getenv('RATELIMIT_BURST_WINDOW', '60'))  # 60 seconds

# Security headers
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
X_FRAME_OPTIONS = 'DENY'

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'app.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'search': {
            'handlers': ['console', 'file'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'api': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Cache configuration
if not DEBUG:
    # Use django-redis in production for distributed caching
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 50,
                    'retry_on_timeout': True,
                },
                'IGNORE_EXCEPTIONS': True,
            },
            'TIMEOUT': 900,  # 15 minutes
        }
    }
else:
    # Use local memory cache in development
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-medlitsearch'
        }
    }

# Proxy configuration (for hospital networks behind proxies)
TRUSTED_PROXIES = [h for h in os.getenv('TRUSTED_PROXIES', '127.0.0.1').split(',') if h]

# Database connection pooling for production
if not DEBUG and os.getenv('DATABASE_URL', '').startswith('postgres'):
    # Add connection pooling with psycopg2
    import dj_database_url
    DATABASES['default'] = dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
