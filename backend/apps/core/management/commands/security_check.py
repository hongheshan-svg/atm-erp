"""
Security check management command.
Performs comprehensive security audit of the system.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run comprehensive security check on the system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix issues where possible',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== ERP System Security Check ===\n'))

        issues = []
        warnings = []
        passed = []

        # 1. Check DEBUG mode
        self.stdout.write('Checking DEBUG mode...')
        if settings.DEBUG:
            issues.append('DEBUG mode is enabled - MUST be disabled in production')
        else:
            passed.append('DEBUG mode is disabled')

        # 2. Check SECRET_KEY
        self.stdout.write('Checking SECRET_KEY...')
        if 'insecure' in settings.SECRET_KEY.lower() or len(settings.SECRET_KEY) < 50:
            issues.append('SECRET_KEY appears to be insecure or too short')
        else:
            passed.append('SECRET_KEY appears secure')

        # 3. Check ALLOWED_HOSTS
        self.stdout.write('Checking ALLOWED_HOSTS...')
        if '*' in settings.ALLOWED_HOSTS:
            issues.append('ALLOWED_HOSTS contains wildcard (*) - security risk')
        elif not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == ['localhost', '127.0.0.1']:
            warnings.append('ALLOWED_HOSTS may need to be configured for production')
        else:
            passed.append('ALLOWED_HOSTS is configured')

        # 4. Check HTTPS settings
        self.stdout.write('Checking HTTPS settings...')
        https_issues = []

        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            https_issues.append('SECURE_SSL_REDIRECT is not enabled')

        if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
            https_issues.append('SESSION_COOKIE_SECURE is not enabled')

        if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            https_issues.append('CSRF_COOKIE_SECURE is not enabled')

        hsts_seconds = getattr(settings, 'SECURE_HSTS_SECONDS', 0)
        if hsts_seconds == 0:
            https_issues.append('HSTS is not enabled (SECURE_HSTS_SECONDS=0)')
        elif hsts_seconds < 31536000:
            warnings.append(f'HSTS duration is short ({hsts_seconds}s), recommend 31536000 (1 year)')

        if https_issues:
            warnings.extend(https_issues)
        else:
            passed.append('HTTPS settings are properly configured')

        # 5. Check database settings
        self.stdout.write('Checking database settings...')
        db_config = settings.DATABASES.get('default', {})

        if db_config.get('PASSWORD') in ['', 'password', 'erp_password']:
            issues.append('Database password appears to be default or empty')
        else:
            passed.append('Database password is set')

        # 6. Check CORS settings
        self.stdout.write('Checking CORS settings...')
        cors_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])

        if '*' in str(cors_origins):
            issues.append('CORS allows all origins - security risk')
        elif not cors_origins:
            warnings.append('CORS_ALLOWED_ORIGINS is not configured')
        else:
            passed.append('CORS is configured')

        # 7. Check password validators
        self.stdout.write('Checking password validators...')
        validators = getattr(settings, 'AUTH_PASSWORD_VALIDATORS', [])

        if len(validators) < 4:
            warnings.append('Consider adding more password validators')
        else:
            passed.append('Password validators are configured')

        # 8. Check for default superuser
        self.stdout.write('Checking for default superuser...')
        User = get_user_model()

        default_admins = User.objects.filter(
            username__in=['admin', 'root', 'administrator'],
            is_superuser=True
        )

        if default_admins.exists():
            warnings.append('Default admin usernames found - consider renaming')
        else:
            passed.append('No default admin usernames found')

        # 9. Check file permissions
        self.stdout.write('Checking file permissions...')
        sensitive_files = [
            settings.BASE_DIR / '.env',
            settings.BASE_DIR.parent / '.env',
        ]

        for filepath in sensitive_files:
            if os.path.exists(filepath):
                mode = oct(os.stat(filepath).st_mode)[-3:]
                if mode not in ['600', '400']:
                    warnings.append(f'{filepath} has permissive permissions ({mode})')

        # 10. Check JWT settings
        self.stdout.write('Checking JWT settings...')
        jwt_settings = getattr(settings, 'SIMPLE_JWT', {})

        access_lifetime = jwt_settings.get('ACCESS_TOKEN_LIFETIME')
        if access_lifetime and access_lifetime.total_seconds() > 7200:  # 2 hours
            warnings.append('JWT access token lifetime is long (>2 hours)')
        else:
            passed.append('JWT token lifetime is reasonable')

        # 11. Check logging configuration
        self.stdout.write('Checking logging configuration...')
        logging_config = getattr(settings, 'LOGGING', {})

        if not logging_config:
            warnings.append('Logging is not configured')
        else:
            passed.append('Logging is configured')

        # 12. Check middleware
        self.stdout.write('Checking security middleware...')
        middleware = getattr(settings, 'MIDDLEWARE', [])

        required_middleware = [
            'django.middleware.security.SecurityMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.middleware.clickjacking.XFrameOptionsMiddleware',
        ]

        missing_middleware = [m for m in required_middleware if m not in middleware]
        if missing_middleware:
            issues.append(f'Missing security middleware: {", ".join(missing_middleware)}')
        else:
            passed.append('Security middleware is configured')

        # Print results
        self.stdout.write('\n' + self.style.MIGRATE_HEADING('=== Results ===\n'))

        if passed:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Passed ({len(passed)}):'))
            for item in passed:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {item}'))

        if warnings:
            self.stdout.write(self.style.WARNING(f'\n⚠ Warnings ({len(warnings)}):'))
            for item in warnings:
                self.stdout.write(self.style.WARNING(f'  ⚠ {item}'))

        if issues:
            self.stdout.write(self.style.ERROR(f'\n✗ Issues ({len(issues)}):'))
            for item in issues:
                self.stdout.write(self.style.ERROR(f'  ✗ {item}'))

        # Summary
        self.stdout.write('\n' + self.style.MIGRATE_HEADING('=== Summary ==='))
        self.stdout.write(f'Passed: {len(passed)}')
        self.stdout.write(f'Warnings: {len(warnings)}')
        self.stdout.write(f'Issues: {len(issues)}')

        if issues:
            self.stdout.write(self.style.ERROR('\n❌ Security check FAILED - please fix issues before deploying to production'))
            return
        elif warnings:
            self.stdout.write(self.style.WARNING('\n⚠ Security check passed with warnings'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Security check PASSED'))
