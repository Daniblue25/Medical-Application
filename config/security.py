"""
Configuration sécurité pour Medical Search App - Site Public Gratuit.
Sécurité sans authentification, optimisée pour déploiement production.
"""

from datetime import timedelta
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============ SÉCURITÉ SSL/HTTPS ============

SECURE_SSL_REDIRECT = not os.getenv('DEBUG', 'false').lower() == 'true'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not os.getenv('DEBUG', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = not os.getenv('DEBUG', 'false').lower() == 'true'
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# ============ HSTS (HTTP Strict Transport Security) ============

SECURE_HSTS_SECONDS = 31536000 if not os.getenv('DEBUG', 'false').lower() == 'true' else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not os.getenv('DEBUG', 'false').lower() == 'true'
SECURE_HSTS_PRELOAD = not os.getenv('DEBUG', 'false').lower() == 'true'

# ============ HEADERS DE SÉCURITÉ ============

SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ("'self'",),
    'script-src': (
        "'self'",
        'https://cdn.jsdelivr.net',
        'https://cdn.tailwindcss.com',
        'https://cdnjs.cloudflare.com',
        'https://cdn.chart.js',
    ),
    'style-src': (
        "'self'",
        "'unsafe-inline'",
        'https://cdn.tailwindcss.com',
        'https://cdnjs.cloudflare.com',
    ),
    'img-src': ("'self'", 'data:', 'https:'),
    'font-src': ("'self'", 'https://cdnjs.cloudflare.com'),
    'connect-src': (
        "'self'",
        'https://eutils.ncbi.nlm.nih.gov',
        'https://www.ncbi.nlm.nih.gov',
    ),
    'frame-ancestors': ("'none'",),
    'base-uri': ("'self'",),
    'form-action': ("'self'",),
}

# ============ RATE LIMITING (sans authentification) ============

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_RATE = '200/h'  # 200 requêtes par heure par IP
REQUEST_TIMEOUT = 30  # Secondes
EXPORT_MAX_ARTICLES = 500  # Max articles à exporter

# ============ IP WHITELIST (optionnel pour CHU) ============

ALLOWED_IP_RANGES = os.getenv('ALLOWED_IP_RANGES', '').split(',') if os.getenv('ALLOWED_IP_RANGES') else []

# ============ CORS POUR SITE PUBLIC ============

CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://localhost:8000',
    'https://127.0.0.1:8000',
]

# Ajouter domaine production si présent
if os.getenv('DOMAIN'):
    domain = os.getenv('DOMAIN')
    CORS_ALLOWED_ORIGINS.extend([
        f'https://{domain}',
        f'https://www.{domain}',
    ])

CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL', 'false').lower() == 'true'
CORS_ALLOW_CREDENTIALS = False
CORS_EXPOSE_HEADERS = ['X-Total-Count', 'X-Page-Count']

# ============ CACHE (sans authentification) ============

CACHE_TIMEOUT = int(os.getenv('CACHE_TIMEOUT', '900'))  # 15 minutes

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'med-search-cache',
        'TIMEOUT': CACHE_TIMEOUT,
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

# ============ PUBMED (PROXY OPTIONNEL) ============

PUBMED_PROXY = os.getenv('PUBMED_PROXY', None)
# Format: 'http://proxy.chu.local:3128' ou 'socks5://127.0.0.1:1080'

# ============ LOGGING DE SÉCURITÉ ============

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Créer répertoire logs s'il n'existe pas
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': LOG_LEVEL,
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'app.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
            'level': LOG_LEVEL,
        },
        'security_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'security.log'),
            'maxBytes': 10485760,
            'backupCount': 20,
            'formatter': 'verbose',
            'level': 'WARNING',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'search': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'security': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    }
}

# ============ STATIC FILES ============

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

print(f"[Security] Mode DEBUG: {os.getenv('DEBUG', 'false')}")
print(f"[Security] HTTPS Redirect: {SECURE_SSL_REDIRECT}")
print(f"[Security] Rate Limit: {RATELIMIT_RATE}")
print(f"[Security] Cache Timeout: {CACHE_TIMEOUT}s")
print(f"[Security] Logging Level: {LOG_LEVEL}")
