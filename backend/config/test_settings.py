"""Tests use explicit, separate PostgreSQL credentials, never DB_* values."""

import os

from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault('SECRET_KEY', 'isolated-lean-test-key-never-for-production-2026')
from .settings import *  # noqa: F403

TESTING = True
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'lean_test_runner',
        'USER': os.environ.get('PG_TEST_USER', ''),
        'PASSWORD': os.environ.get('PG_TEST_PASSWORD', ''),
        'HOST': os.environ.get('PG_TEST_HOST', ''),
        'PORT': os.environ.get('PG_TEST_PORT', '5432'),
        'TEST': {'NAME': 'test_atm_erp_lean'},
    }
}
if not all(DATABASES['default'][key] for key in ('USER', 'PASSWORD', 'HOST')):
    raise ImproperlyConfigured('测试必须显式配置 PG_TEST_HOST、PG_TEST_USER、PG_TEST_PASSWORD。')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
