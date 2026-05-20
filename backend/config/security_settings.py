"""
Security settings for production deployment.
Import this file in settings.py for production environments.
"""

from decouple import config

# =============================================================================
# HTTPS / SSL Settings
# =============================================================================

# Force HTTPS in production
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)  # Set to 31536000 (1 year) in production
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)

# Secure cookies
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)

# Proxy SSL header (for nginx/load balancer)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# =============================================================================
# Content Security Policy
# =============================================================================

# X-Content-Type-Options
SECURE_CONTENT_TYPE_NOSNIFF = True

# X-Frame-Options (prevent clickjacking)
X_FRAME_OPTIONS = 'DENY'

# XSS Protection
SECURE_BROWSER_XSS_FILTER = True

# =============================================================================
# CSRF Settings
# =============================================================================

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost,http://127.0.0.1',
    cast=lambda v: [s.strip() for s in v.split(',')],
)

# =============================================================================
# Session Security
# =============================================================================

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# =============================================================================
# Password Policy Settings
# =============================================================================

PASSWORD_MIN_LENGTH = config('PASSWORD_MIN_LENGTH', default=8, cast=int)
PASSWORD_REQUIRE_UPPERCASE = config('PASSWORD_REQUIRE_UPPERCASE', default=True, cast=bool)
PASSWORD_REQUIRE_LOWERCASE = config('PASSWORD_REQUIRE_LOWERCASE', default=True, cast=bool)
PASSWORD_REQUIRE_DIGIT = config('PASSWORD_REQUIRE_DIGIT', default=True, cast=bool)
PASSWORD_REQUIRE_SPECIAL = config('PASSWORD_REQUIRE_SPECIAL', default=True, cast=bool)
PASSWORD_EXPIRY_DAYS = config('PASSWORD_EXPIRY_DAYS', default=90, cast=int)
PASSWORD_HISTORY_COUNT = config('PASSWORD_HISTORY_COUNT', default=5, cast=int)

# Account lockout
MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)
LOCKOUT_DURATION_MINUTES = config('LOCKOUT_DURATION_MINUTES', default=30, cast=int)

# =============================================================================
# Rate Limiting
# =============================================================================

# DRF Throttling
REST_FRAMEWORK_THROTTLE_RATES = {
    'anon': '100/hour',
    'user': '1000/hour',
    'login': '5/minute',
    'password_reset': '3/hour',
}

# =============================================================================
# File Upload Security
# =============================================================================

# Maximum upload size (100MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600

# Allowed file extensions
ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf',
    '.doc',
    '.docx',
    '.xls',
    '.xlsx',
    '.ppt',
    '.pptx',
    '.txt',
    '.csv',
    '.json',
    '.xml',
    '.jpg',
    '.jpeg',
    '.png',
    '.gif',
    '.bmp',
    '.svg',
    '.zip',
    '.rar',
    '.7z',
    '.tar',
    '.gz',
]

# =============================================================================
# API Security
# =============================================================================

# JWT Token settings (more secure for production)
SIMPLE_JWT_PRODUCTION = {
    'ACCESS_TOKEN_LIFETIME': config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=30, cast=int),
    'REFRESH_TOKEN_LIFETIME': config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=1, cast=int),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': config('SECRET_KEY'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# =============================================================================
# Logging Security Events
# =============================================================================

SECURITY_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '[SECURITY] {levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/security.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'security',
        },
    },
    'loggers': {
        'security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
