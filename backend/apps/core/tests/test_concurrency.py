from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.models import ActionReceipt, CodeRule
from apps.core.permissions import ADMIN, require_role


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql', '并发验证必须运行在 PostgreSQL。')
        self.actor = User.objects.create_user(username='admin', role='admin')
        CodeRule.objects.create(key='project', prefix='PRJ')

    def concurrent_codes(self, keys):
        barrier = Barrier(len(keys))

        def execute(key):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                return perform(
                    actor=actor,
                    key=key,
                    operation='code',
                    payload={},
                    authorize=lambda user: require_role(user, ADMIN),
                    execute=lambda user: {'code': CodeRule.generate_code('project')},
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(keys)) as pool:
            return list(pool.map(execute, keys))

    def test_same_operation_is_executed_once(self):
        results = self.concurrent_codes(['same'] * 4)
        self.assertEqual(results, [{'code': 'PRJ000001'}] * 4)
        self.assertEqual(CodeRule.objects.get(key='project').counter, 1)
        self.assertEqual(ActionReceipt.objects.count(), 1)

    def test_different_operations_receive_unique_codes(self):
        results = self.concurrent_codes(['one', 'two', 'three', 'four'])
        self.assertEqual(len({result['code'] for result in results}), 4)
        self.assertEqual(CodeRule.objects.get(key='project').counter, 4)

    def test_concurrent_period_rollover_resets_only_once(self):
        from django.utils import timezone

        CodeRule.objects.filter(key='project').update(
            date_format='YYYYMMDD', reset_cycle='day', period='20000101', counter=900, padding=3
        )
        results = self.concurrent_codes(['a', 'b', 'c', 'd'])
        prefix = 'PRJ' + timezone.localdate().strftime('%Y%m%d')
        self.assertEqual({r['code'] for r in results}, {f'{prefix}{i:03d}' for i in range(1, 5)})
