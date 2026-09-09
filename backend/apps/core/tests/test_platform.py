import io
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import ActionReceipt, AuditLog, CodeRule, Company, SchemaVersion
from apps.core.permissions import ADMIN, require_role
from apps.core.schema_guard import check_schema


class PlatformTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(username='admin', password='Foundation-Tests-672', role='admin')
        CodeRule.objects.create(key='project', prefix='PRJ')

    def action(self, key='one', payload=None, execute=None):
        return perform(
            actor=self.actor,
            key=key,
            operation='project.code',
            payload=payload or {},
            authorize=lambda user: require_role(user, ADMIN),
            execute=execute or (lambda user: {'code': CodeRule.generate_code('project')}),
        )

    def test_replay_does_not_generate_second_code(self):
        first = self.action()
        self.assertEqual(first, self.action())
        self.assertEqual(CodeRule.objects.get(key='project').counter, 1)
        self.assertEqual(ActionReceipt.objects.count(), 1)

    def test_same_key_cannot_change_payload(self):
        self.action(payload={'value': 1})
        with self.assertRaises(Conflict):
            self.action(payload={'value': 2})

    def test_replay_rechecks_persisted_role(self):
        self.action()
        User.objects.filter(pk=self.actor.pk).update(role='member')
        with self.assertRaises(PermissionDenied):
            self.action()

    def test_replay_rechecks_active_status(self):
        self.action()
        User.objects.filter(pk=self.actor.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.action()

    def test_action_failure_rolls_back_receipt_and_business_write(self):
        def fail(user):
            CodeRule.generate_code('project')
            raise ValidationError('模拟校验失败')

        with self.assertRaises(ValidationError):
            self.action(execute=fail)
        self.assertFalse(ActionReceipt.objects.exists())
        self.assertEqual(CodeRule.objects.get(key='project').counter, 0)
        self.assertEqual(self.action()['code'], 'PRJ000001')

    def test_action_key_is_required(self):
        for key in ['', ' ', 'x' * 129, None]:
            with self.subTest(key=key), self.assertRaises(ValidationError):
                self.action(key=key)

    def test_schema_accepts_migrated_database(self):
        SchemaVersion.objects.update_or_create(pk=1, defaults={'generation': 'lean-erp-v1'})
        check_schema()

    def test_schema_rejects_legacy_table_without_dropping_it(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE legacy_sales_order (id integer)')
        with self.assertRaises(CommandError):
            check_schema(migrating=True)
        self.assertIn('legacy_sales_order', connection.introspection.table_names())

    def test_schema_rejects_wrong_marker(self):
        SchemaVersion.objects.update_or_create(pk=1, defaults={'generation': 'old-version'})
        for migrating in (False, True):
            with self.subTest(migrating=migrating), self.assertRaises(CommandError):
                check_schema(migrating=migrating)

    def test_schema_rejects_legacy_migration_history(self):
        from django.db.migrations.recorder import MigrationRecorder

        MigrationRecorder(connection).record_applied('sales', '0099_legacy')
        with self.assertRaises(CommandError):
            check_schema(migrating=True)

    def test_schema_requires_marker_for_runtime(self):
        SchemaVersion.objects.all().delete()
        with self.assertRaises(CommandError):
            check_schema()

    @override_settings(TESTING=False)
    def test_migrate_refuses_fake_and_targeted_commands(self):
        for options in (
            {'fake': True},
            {'fake_initial': True},
            {'prune': True},
            {'app_label': 'accounts'},
            {'run_syncdb': True},
        ):
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command('migrate', stdout=io.StringIO(), **options)

    @override_settings(TESTING=False)
    def test_flush_is_forbidden_outside_test_settings(self):
        with self.assertRaises(CommandError):
            call_command('flush', interactive=False, stdout=io.StringIO())


class InitializationTests(TestCase):
    def test_requires_password_and_rolls_back_all_initial_records(self):
        SchemaVersion.objects.update_or_create(pk=1, defaults={'generation': 'lean-erp-v1'})
        with patch.dict('os.environ', {'ADMIN_PASSWORD': ''}), self.assertRaises(CommandError):
            call_command('init_system', stdout=io.StringIO())
        self.assertFalse(User.objects.exists())
        self.assertFalse(Company.objects.exists())
        self.assertFalse(CodeRule.objects.exists())

    def test_initialization_is_repeatable_without_resetting_password(self):
        SchemaVersion.objects.update_or_create(pk=1, defaults={'generation': 'lean-erp-v1'})
        with patch.dict('os.environ', {'ADMIN_PASSWORD': 'Fresh-Install-Tests-782'}):
            call_command('init_system', stdout=io.StringIO())
        user = User.objects.get(username='admin')
        first_hash = user.password
        self.assertTrue(user.check_password('Fresh-Install-Tests-782'))
        self.assertEqual(CodeRule.generate_code('project'), 'PRJ000001')
        with patch.dict('os.environ', {'ADMIN_PASSWORD': 'Another-Install-Tests-899'}):
            call_command('init_system', stdout=io.StringIO())
        user.refresh_from_db()
        self.assertEqual(user.password, first_hash)
        self.assertEqual(CodeRule.objects.count(), 6)
        self.assertEqual(CodeRule.objects.get(key='project').counter, 1)
        self.assertEqual(AuditLog.objects.count(), 1)
