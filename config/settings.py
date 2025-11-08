"""
Django settings for Ayende CX project.
WITH CUSTOM DOMAIN SUPPORT
"""

import os
from pathlib import Path
# Load environment variables from .env file
from dotenv import load_dotenv

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent
# Load .env file from project root
load_dotenv(BASE_DIR / '.env')

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', '31YMBwf4R4OetvSJ/nIf+5D1ndnMxruRL1QcJsCM9jM=')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Custom domain configuration
CUSTOM_DOMAIN = os.environ.get('CUSTOM_DOMAIN', '')  # e.g., 'ayendecx.com'

# Build allowed hosts
allowed_hosts = ['.railway.app', 'localhost', '127.0.0.1', '.localhost']

if CUSTOM_DOMAIN:
    allowed_hosts.extend([
        CUSTOM_DOMAIN,
        f'.{CUSTOM_DOMAIN}',  # Wildcard for subdomains
    ])

ALLOWED_HOSTS = ['.ayendecx.com', 'staging.ayendecx.com', 'ayendecx.com']


# Application definition
INSTALLED_APPS = [
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'tenants',
    'customers',
    'dashboard',
    'notifications',
    'rewards',
    'profile',
    'reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Always include, works in both dev and prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tenants.middleware.TenantMiddleware',
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
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Static files directories - needed in BOTH dev and production
STATICFILES_DIRS = [BASE_DIR / 'static']

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
    
# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'customers.Customer'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'tenants.backends.TenantAwareAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ===== EMAIL CONFIGURATION - SENDGRID =====
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'  # This is literally the word "apikey"
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')
DEFAULT_FROM_EMAIL = 'noreply@ayendecx.com'  # Match your verified sender exactly
SERVER_EMAIL = 'noreply@ayendecx.com'
EMAIL_TIMEOUT = 30

# Security settings for production
ENABLE_HTTPS_REDIRECT = os.environ.get('ENABLE_HTTPS_REDIRECT', 'False') == 'True'

if not DEBUG and ENABLE_HTTPS_REDIRECT:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# CSRF trusted origins - Include custom domain
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.ayendecx.com',
]

if CUSTOM_DOMAIN:
    CSRF_TRUSTED_ORIGINS.extend([
        f'https://{CUSTOM_DOMAIN}',
        f'https://*.{CUSTOM_DOMAIN}',
    ])

# Cookie domain configuration for multi-tenant subdomains
if CUSTOM_DOMAIN and not DEBUG:
    SESSION_COOKIE_DOMAIN = f'.{CUSTOM_DOMAIN}'
    CSRF_COOKIE_DOMAIN = f'.{CUSTOM_DOMAIN}'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Modern Admin Dashboard
UNFOLD = {
    "SITE_TITLE": "Ayende CX",
    "SITE_HEADER": "Ayende CX Admin",
    "SITE_URL": "/",
    "SITE_ICON": None,
    "SITE_LOGO": None,
    "SITE_SYMBOL": "analytics",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "ENVIRONMENT": "production" if not DEBUG else "development",
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
}

# Loyalty Settings
LOYALTY_POINTS_PER_DOLLAR = 0.1  # 1 point per $10 spent

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
# ============================================
# POS INTEGRATION SETTINGS
# ============================================
INTEGRATION_SECRET = '31YMBwf4R4OetvSJ/nIf+5D1ndnMxruRL1QcJsCM9jM='  # IMPORTANT: Change this!
POS_API_URL = os.getenv('POS_API_URL', 'https://pos-staging.ayendecx.com')  # POS backend URL
POS_API_TIMEOUT = int(os.getenv('POS_API_TIMEOUT', '30000'))
ENABLE_CUSTOMER_SYNC_TO_POS = os.getenv('ENABLE_CUSTOMER_SYNC_TO_POS', 'True').lower() == 'true'
CUSTOMER_SYNC_INTERVAL = int(os.getenv('CUSTOMER_SYNC_INTERVAL', '3600'))
SYNC_BATCH_SIZE = int(os.getenv('SYNC_BATCH_SIZE', '100'))
ENABLE_POS_SYNC = True
ENABLE_CRM_SYNC = True
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'  # Literally the word "apikey"
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@ayendecx.com')

#**Railway Variables:**

# ===== PHASE 2C: Webhook Configuration =====

# POS Webhook URL (base URL for POS system)
POS_WEBHOOK_URL = os.getenv('POS_WEBHOOK_URL', 'https://pos-staging.ayendecx.com')

# Enable/disable webhook sending
ENABLE_WEBHOOKS = True

# Webhook retry configuration
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_TIMEOUT = 10  # seconds

# Webhook security
# IMPORTANT: This must match INTEGRATION_SECRET in POS .env file
INTEGRATION_SECRET = os.environ.get('INTEGRATION_SECRET', '31YMBwf4R4OetvSJ/nIf+5D1ndnMxruRL1QcJsCM9jM=')

# ===== End Phase 2C Configuration =====
# ===== PHASE 2C: Webhook Configuration =====

# POS Webhook URL (base URL for POS system)
POS_WEBHOOK_URL = os.getenv('POS_WEBHOOK_URL', 'https://pos-staging.ayendecx.com')

# Enable CRM sync and webhooks
ENABLE_CRM_SYNC = True  # This enables webhooks
ENABLE_WEBHOOKS = True  # Additional toggle

# Webhook retry configuration
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_TIMEOUT = 10  # seconds

# Webhook security - must match POS .env
INTEGRATION_SECRET = os.environ.get('INTEGRATION_SECRET', 'your-shared-secret-key-change-this')

# ===== End Phase 2C Configuration =====