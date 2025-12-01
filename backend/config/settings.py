"""
Django settings for ERP project.
"""
from pathlib import Path
from datetime import timedelta
from decouple import config

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
# SECURITY WARNING: In production, set SECRET_KEY via environment variable
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
# Default is False for security - must explicitly enable for development
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
INSTALLED_APPS = [
    'daphne',  # Must be first for ASGI
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    'django_extensions',
    'channels',
    'django_elasticsearch_dsl',
    'django_elasticsearch_dsl_drf',
    
    # Local apps
    'apps.core',
    'apps.core.workflow',
    'apps.accounts',
    'apps.masterdata',
    'apps.projects',
    'apps.purchase',
    'apps.sales',
    'apps.inventory',
    'apps.finance',
    'apps.reports',
    'apps.analytics',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.AuditLogMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
ASGI_APPLICATION = 'config.asgi.application'

# Channels configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(config('REDIS_HOST', default='redis'), 6379)],
        },
    },
}

# Elasticsearch configuration
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': config('ELASTICSEARCH_HOST', default='elasticsearch:9200')
    },
}

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='erp_db'),
        'USER': config('DB_USER', default='erp_user'),
        'PASSWORD': config('DB_PASSWORD', default='erp_password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
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
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR.parent / 'uploads'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    # Rate limiting
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_LIFETIME_MINUTES', default=120, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,  # Enable token blacklist for security
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# CORS Settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOW_CREDENTIALS = True

# Cache settings (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://redis:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# API Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'ERP System API',
    'DESCRIPTION': 'Enterprise Resource Planning System - Project Management, PSI & Cost Control',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Logging
import os
LOG_DIR = BASE_DIR.parent / 'logs'
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

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
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# =============================================================================
# Notification Settings (DingTalk / WeChat Work)
# =============================================================================

# DingTalk (钉钉) Configuration
DINGTALK_WEBHOOK_URL = config('DINGTALK_WEBHOOK_URL', default='')
DINGTALK_WEBHOOK_SECRET = config('DINGTALK_WEBHOOK_SECRET', default='')
DINGTALK_APP_KEY = config('DINGTALK_APP_KEY', default='')
DINGTALK_APP_SECRET = config('DINGTALK_APP_SECRET', default='')
DINGTALK_AGENT_ID = config('DINGTALK_AGENT_ID', default='')

# WeChat Work (企业微信) Configuration
WECHAT_WORK_WEBHOOK_URL = config('WECHAT_WORK_WEBHOOK_URL', default='')
WECHAT_WORK_CORP_ID = config('WECHAT_WORK_CORP_ID', default='')
WECHAT_WORK_CORP_SECRET = config('WECHAT_WORK_CORP_SECRET', default='')
WECHAT_WORK_AGENT_ID = config('WECHAT_WORK_AGENT_ID', default='')

# Frontend URL for notification links
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost')

# Enable notification channels
NOTIFICATION_CHANNELS_ENABLED = config(
    'NOTIFICATION_CHANNELS_ENABLED',
    default='email',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# =============================================================================
# Inventory Costing Method
# =============================================================================
# Options: 'WEIGHTED_AVG' (default), 'FIFO'
INVENTORY_COSTING_METHOD = config('INVENTORY_COSTING_METHOD', default='WEIGHTED_AVG')

# =============================================================================
# Security Settings (Production)
# =============================================================================

# HTTPS Settings - Enable in production
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS Settings
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)

# Cookie Security
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://localhost:5173',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Password Policy Settings
PASSWORD_MIN_LENGTH = config('PASSWORD_MIN_LENGTH', default=8, cast=int)
PASSWORD_REQUIRE_UPPERCASE = config('PASSWORD_REQUIRE_UPPERCASE', default=True, cast=bool)
PASSWORD_REQUIRE_LOWERCASE = config('PASSWORD_REQUIRE_LOWERCASE', default=True, cast=bool)
PASSWORD_REQUIRE_DIGIT = config('PASSWORD_REQUIRE_DIGIT', default=True, cast=bool)
PASSWORD_REQUIRE_SPECIAL = config('PASSWORD_REQUIRE_SPECIAL', default=True, cast=bool)
PASSWORD_EXPIRY_DAYS = config('PASSWORD_EXPIRY_DAYS', default=90, cast=int)

# Login Security
MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)
LOCKOUT_DURATION_MINUTES = config('LOCKOUT_DURATION_MINUTES', default=30, cast=int)

