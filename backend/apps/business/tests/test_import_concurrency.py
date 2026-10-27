"""Real PostgreSQL sessions for import lock ordering and confirmation races."""

import csv
import io
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase
from rest_framework.exceptions import APIException, PermissionDenied

from apps.accounts.models import User
from apps.business.models import BOMLine, Entry, Item, Partner, Payment, Project, Stock, StockMove, Task, TimeEntry
from apps.business.services import bom_import, bom_material_import, execution, masterdata, supply, transfers
from apps.core.api import Conflict
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


class ImportConcurrencyTests(BusinessFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_business()
        self.first = self.active_project()
        self.second = self.active_project()

    def token(self, projects, title):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow([label for label, _ in transfers.SCHEMAS['entries'][1]])
        for project in projects:
            writer.writerow([project.code, title, '10', TODAY])
        result = transfers.preview(
            self.users['finance'], 'entries', SimpleUploadedFile('expenses.csv', stream.getvalue().encode())
        )
        self.assertTrue(result['can_import'], result)
        return result['token']

    def wait_for_lock(self, pid):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s', [pid])
                if cursor.fetchone() == ('Lock',):
                    return
            time.sleep(0.02)
        self.fail('并发导入未进入预期的数据库锁等待。')

    def race_batches(self):
        reverse = self.token([self.second, self.first], '逆序导入')
        ascending = self.token([self.first, self.second], '升序导入')
        ready, context = Event(), {}

        def import_reverse():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '12s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    context['pid'] = cursor.fetchone()[0]
                ready.set()
                return transfers.confirm(User.objects.get(pk=self.users['finance'].pk), 'entries', reverse)
            finally:
                connections.close_all()

        errors = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            try:
                with transaction.atomic():
                    # A monthly operation / ascending import already owns the first project.
                    Project.objects.select_for_update().get(pk=self.first.pk)
                    future = pool.submit(import_reverse)
                    self.assertTrue(ready.wait(5))
                    self.wait_for_lock(context['pid'])
                    transfers.confirm(self.users['finance'], 'entries', ascending)
            except Exception as exc:  # Preserve actual database exception in failure evidence.
                errors.append(exc)
            try:
                self.assertEqual(future.result(timeout=15)['count'], 2)
            except Exception as exc:
                errors.append(exc)
        return errors

    def test_legacy_row_locks_reproduce_database_deadlock(self):
        # Control case: execute the same real services without batch pre-locking.
        # PostgreSQL, not an exception mock, must detect the original lock cycle.
        with patch.object(transfers, 'lock_batch', return_value=[]):
            errors = self.race_batches()
        deadlocks = [
            error
            for error in errors
            if getattr(error.__cause__, 'sqlstate', getattr(error.__cause__, 'pgcode', None)) == '40P01'
        ]
        self.assertEqual(len(deadlocks), 1, repr(errors))
        self.assertEqual(Entry.objects.filter(kind='expense').count(), 2)

    def test_reversed_project_import_and_ascending_batch_do_not_deadlock(self):
        errors = self.race_batches()
        self.assertEqual(errors, [], repr(errors))
        self.assertEqual(Entry.objects.filter(kind='expense').count(), 4)

    def test_payment_batches_with_reversed_accounts_prelock_before_first_write(self):
        first_entry, second_entry = self.first.entries.get(), self.second.entries.get()

        def preview(entry, accounts):
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow([label for label, _ in transfers.SCHEMAS['payments'][1]])
            for account in accounts:
                writer.writerow([entry.pk, '10', TODAY, '批量收款', 'bank', account, f'{entry.pk}-{account}', '', ''])
            result = transfers.preview(
                self.users['finance'], 'payments', SimpleUploadedFile('payments.csv', stream.getvalue().encode())
            )
            self.assertTrue(result['can_import'], result)
            return result['token']

        first_token = preview(first_entry, ['ACCOUNT-A', 'ACCOUNT-B'])
        second_token = preview(second_entry, ['ACCOUNT-B', 'ACCOUNT-A'])
        first_write, release, started = Event(), Event(), Event()
        backend = {}
        original_save = Payment.save

        def hold_first(payment, *args, **kwargs):
            if payment.entry_id == first_entry.pk and not first_write.is_set():
                first_write.set()
                if not release.wait(12):
                    raise AssertionError('首批收款未收到释放信号。')
            return original_save(payment, *args, **kwargs)

        def confirm(token, competing=False):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '12s'")
                    if competing:
                        cursor.execute('SELECT pg_backend_pid()')
                        backend['pid'] = cursor.fetchone()[0]
                        started.set()
                return transfers.confirm(self.users['finance'], 'payments', token)
            finally:
                connections.close_all()

        with patch.object(Payment, 'save', hold_first), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(confirm, first_token)
            try:
                self.assertTrue(first_write.wait(8))
                second = pool.submit(confirm, second_token, True)
                self.assertTrue(started.wait(8))
                self.wait_for_lock(backend['pid'])
            finally:
                release.set()
            self.assertEqual(first.result(timeout=15)['count'], 2)
            self.assertEqual(second.result(timeout=15)['count'], 2)
        self.assertEqual(Payment.objects.count(), 4)
        for entry in [first_entry, second_entry]:
            self.assertEqual(sum(entry.payments.values_list('amount', flat=True)), Decimal('20'))

    def test_issue_import_prelocks_all_projects_before_item_lock_during_receipt(self):
        stock = Stock.objects.create(item=self.item, location='主仓', quantity=10, value=100)
        for project in [self.first, self.second]:
            BOMLine.objects.create(project=project, item=self.item, quantity=2)
        purchase = self.purchase(self.first, qty='1', price='10')
        line = purchase.lines.get()
        stream = io.StringIO()
        writer = csv.writer(stream)
        columns = transfers.SCHEMAS['moves'][1]
        writer.writerow([label for label, _ in columns])
        for project in [self.second, self.first]:
            row = {'project': project.code, 'stock': str(stock.pk), 'quantity': '1', 'reason': '导入领料'}
            writer.writerow([row.get(key, '') for _, key in columns])
        preview = transfers.preview(
            self.users['admin'], 'moves', SimpleUploadedFile('moves.csv', stream.getvalue().encode())
        )
        self.assertTrue(preview['can_import'], preview)
        ready, context = Event(), {}

        def import_moves():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '12s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    context['pid'] = cursor.fetchone()[0]
                ready.set()
                return transfers.confirm(User.objects.get(pk=self.users['admin'].pk), 'moves', preview['token'])
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Project.objects.select_for_update().get(pk=self.first.pk)
                future = pool.submit(import_moves)
                self.assertTrue(ready.wait(5))
                self.wait_for_lock(context['pid'])
                supply.receive(
                    self.users['warehouse'],
                    'concurrent-receipt',
                    purchase.pk,
                    {
                        'location': '主仓',
                        'lines': [{'line': line.pk, 'quantity': '1'}],
                        'received_date': TODAY,
                        'backfill_reason': '并发测试补录历史采购收货，已核对原始收货记录。',
                        'reason': '并发收货',
                    },
                )
            self.assertEqual(future.result(timeout=15)['count'], 2)
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 9)
        self.assertEqual(StockMove.objects.filter(kind='issue').count(), 2)
        self.assertEqual(StockMove.objects.filter(kind='receipt').count(), 1)
        replay = transfers.confirm(self.users['admin'], 'moves', preview['token'])
        self.assertEqual(replay['count'], 2)
        self.assertEqual(StockMove.objects.filter(kind='issue').count(), 2)

    def test_bom_material_import_and_item_edit_lock_code_rule_before_item(self):
        # 物料导入确认先锁物料编码规则、再由 BOM 修订锁物料；编辑物料必须同序，
        # 否则真实 PostgreSQL 会检测到锁环（40P01），其中一方返回 500。
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(bom_material_import.HEADERS)
        writer.writerow([self.item.code, '', '2', '导入现有物料', *[''] * (len(bom_material_import.HEADERS) - 4)])
        preview = bom_material_import.preview(
            self.users['manager'], self.first, SimpleUploadedFile('bom.csv', stream.getvalue().encode())
        )
        self.assertTrue(preview['can_import'], preview)
        holding, release, ready, context = Event(), Event(), Event(), {}
        original = bom_import.preview

        def held_preview(project, upload):
            # resolve() 已持有 CodeRule('item')，revise_bom 还没有锁物料。
            holding.set()
            if not release.wait(10):
                raise RuntimeError('等待物料编辑进入锁等待超时。')
            return original(project, upload)

        def session(action, name=None):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '12s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    if name:
                        context[name] = cursor.fetchone()[0]
                        ready.set()
                return action()
            except Exception as exc:  # Keep the real database error as test evidence.
                return exc
            finally:
                connections.close_all()

        def confirm():
            return bom_material_import.confirm(
                User.objects.get(pk=self.users['manager'].pk),
                Project.objects.get(pk=self.first.pk),
                {'token': preview['token']},
            )

        def edit():
            return masterdata.masterdata(
                User.objects.get(pk=self.users['admin'].pk),
                'edit-during-import',
                Item,
                {'brand': '新品牌'},
                self.item.pk,
            )

        with patch.object(bom_import, 'preview', held_preview), ThreadPoolExecutor(max_workers=2) as pool:
            importing = pool.submit(session, confirm)
            self.assertTrue(holding.wait(10))
            editing = pool.submit(session, edit, 'edit')
            self.assertTrue(ready.wait(5))
            self.wait_for_lock(context['edit'])
            release.set()
            results = [importing.result(timeout=30), editing.result(timeout=30)]
        self.assertTrue(all(isinstance(result, dict) for result in results), repr(results))
        self.assertEqual(BOMLine.objects.get(project=self.first, item=self.item).quantity, 2)
        self.assertEqual(Item.objects.get(pk=self.item.pk).brand, '新品牌')

    def test_cross_user_equivalent_content_confirmation_is_serialized(self):
        stream = io.StringIO()
        columns = transfers.SCHEMAS['partners'][1]
        row = {'name': '并发导入供应商', 'kind': 'supplier'}
        writer = csv.writer(stream)
        writer.writerow([label for label, _ in columns])
        writer.writerow([row.get(key, '') for _, key in columns])
        previews = [
            transfers.preview(
                self.users[role], 'partners', SimpleUploadedFile('partners.csv', stream.getvalue().encode())
            )
            for role in ('admin', 'purchaser')
        ]
        for preview in previews:
            self.assertTrue(preview['can_import'], preview)
        first_executing, release, second_ready = Event(), Event(), Event()
        context = {}
        original_run = transfers.run

        def scheduled_run(*args, **kwargs):
            first_executing.set()
            if not release.wait(10):
                raise TimeoutError('未释放并发导入测试屏障。')
            return original_run(*args, **kwargs)

        def confirm(index):
            close_old_connections()
            try:
                if index == 1:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_backend_pid()')
                        context['pid'] = cursor.fetchone()[0]
                    second_ready.set()
                role = ('admin', 'purchaser')[index]
                return transfers.confirm(User.objects.get(pk=self.users[role].pk), 'partners', previews[index]['token'])
            except Conflict as exc:
                return exc
            finally:
                connections.close_all()

        with patch.object(transfers, 'run', side_effect=scheduled_run), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(confirm, 0)
            try:
                self.assertTrue(first_executing.wait(5))
                second = pool.submit(confirm, 1)
                self.assertTrue(second_ready.wait(5))
                self.wait_for_lock(context['pid'])
            finally:
                release.set()
            self.assertEqual(first.result(timeout=15)['count'], 1)
            self.assertIsInstance(second.result(timeout=15), Conflict)
        self.assertEqual(Partner.objects.filter(name=row['name']).count(), 1)
        self.assertEqual(ActionReceipt.objects.filter(operation='import.partners').count(), 1)

    def test_same_token_concurrent_requests_with_different_keys_return_one_batch(self):
        token = self.token([self.first, self.second], '同凭据并发重试')
        start = Barrier(2)

        def confirm(index):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.users['finance'].pk)
                start.wait(timeout=5)
                return transfers.confirm(actor, 'entries', token, key=f'concurrent-request-{index}')
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(confirm, index) for index in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(Entry.objects.filter(kind='expense').count(), 2)
        self.assertEqual(ActionReceipt.objects.filter(operation='import.entries').count(), 1)

    def time_preview(self, actor, task, person, hours='1'):
        columns = transfers.SCHEMAS['time'][1]
        row = {'task': str(task.pk), 'user': person.username, 'date': TODAY, 'hours': hours, 'reason': '并发工时'}
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow([label for label, _ in columns])
        writer.writerow([row.get(key, '') for _, key in columns])
        preview = transfers.preview(actor, 'time', SimpleUploadedFile('time.csv', stream.getvalue().encode()))
        self.assertTrue(preview['can_import'], preview)
        return preview['token']

    def parallel_time(self, actions, *, synchronize_writes=False):
        start, written = Barrier(2), Barrier(2)
        original_audit = execution.audit

        def audit_together(*args, **kwargs):
            result = original_audit(*args, **kwargs)
            if synchronize_writes:
                # Both real transactions have saved their own person's time and audit FKs.
                # Commit together: FOR UPDATE reproduces 40P01; NO KEY UPDATE must permit both.
                written.wait(timeout=6)
            return result

        def run(action):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '10s'")
                start.wait(timeout=6)
                return action()
            except Exception as exc:
                return exc
            finally:
                connections.close_all()

        with patch.object(execution, 'audit', side_effect=audit_together), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, action) for action in actions]
            return [future.result(timeout=15) for future in futures]

    def cross_actor_time(self, other_action):
        actor_a, actor_b = self.users['admin'], self.users['manager']
        task_a = Task.objects.create(project=self.first, title='交叉A', kind='design', assignee=actor_b)
        task_b = Task.objects.create(project=self.second, title='交叉B', kind='design', assignee=actor_a)
        token_a = self.time_preview(actor_a, task_a, actor_b)
        if other_action == 'import':
            token_b = self.time_preview(actor_b, task_b, actor_a)

            def second():
                return transfers.confirm(actor_b, 'time', token_b)
        elif other_action == 'single':

            def second():
                return execution.log_time(
                    actor_b,
                    'cross-single',
                    task_b.pk,
                    {
                        'user': actor_a.pk,
                        'date': TODAY,
                        'hours': '1',
                        'reason': '交叉单笔登记',
                    },
                )
        else:
            original = execution.log_time(
                actor_b,
                'cross-original',
                task_b.pk,
                {
                    'user': actor_a.pk,
                    'date': TODAY,
                    'hours': '1',
                    'reason': '原登记',
                },
            )

            def second():
                return execution.amend_time(
                    actor_b,
                    'cross-amend',
                    original['id'],
                    {
                        'date': TODAY,
                        'hours': '2',
                        'reason': '交叉更正',
                    },
                )

        baseline = (TimeEntry.objects.count(), ActionReceipt.objects.count(), AuditLog.objects.count())
        results = self.parallel_time(
            [
                lambda: transfers.confirm(actor_a, 'time', token_a),
                second,
            ],
            synchronize_writes=True,
        )
        self.assertTrue(all(isinstance(result, dict) for result in results), repr(results))
        deltas = tuple(
            after - before
            for after, before in zip(
                (TimeEntry.objects.count(), ActionReceipt.objects.count(), AuditLog.objects.count()),
                baseline,
                strict=True,
            )
        )
        self.assertEqual(deltas, (3 if other_action == 'amend' else 2, 4 if other_action == 'import' else 3, 2))
        self.assertEqual(sum(TimeEntry.objects.values_list('hours', flat=True)), 3 if other_action == 'amend' else 2)
        self.assertEqual(transfers.confirm(actor_a, 'time', token_a), results[0])
        self.assertEqual(second(), results[1])
        self.assertEqual(TimeEntry.objects.count() - baseline[0], deltas[0])

    def test_cross_actor_time_imports_commit_without_foreign_key_deadlock(self):
        self.cross_actor_time('import')

    def test_time_import_and_single_time_commit_without_foreign_key_deadlock(self):
        self.cross_actor_time('single')

    def test_time_import_and_amendment_commit_without_foreign_key_deadlock(self):
        self.cross_actor_time('amend')

    def daily_limit_race(self, amend=False):
        actor, person = self.users['admin'], self.users['member']
        task_a = Task.objects.create(project=self.first, title='限额A', kind='design', assignee=person)
        task_b = Task.objects.create(project=self.second, title='限额B', kind='design', assignee=person)
        if amend:
            original = execution.log_time(
                actor,
                'daily-original',
                task_b.pk,
                {
                    'user': person.pk,
                    'date': TODAY,
                    'hours': '3',
                    'reason': '原登记',
                },
            )

            def second():
                return execution.amend_time(
                    actor,
                    'daily-amend',
                    original['id'],
                    {
                        'date': TODAY,
                        'hours': '15',
                        'reason': '并发更正',
                    },
                )
        else:

            def second():
                return execution.log_time(
                    actor,
                    'daily-single',
                    task_b.pk,
                    {
                        'user': person.pk,
                        'date': TODAY,
                        'hours': '15',
                        'reason': '并发登记',
                    },
                )

        token = self.time_preview(actor, task_a, person, hours='15')
        baseline = (TimeEntry.objects.count(), ActionReceipt.objects.count(), AuditLog.objects.count())
        results = self.parallel_time([lambda: transfers.confirm(actor, 'time', token), second])
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1, repr(results))
        self.assertEqual(sum(isinstance(result, APIException) for result in results), 1, repr(results))
        self.assertIn('24', str(next(result for result in results if isinstance(result, APIException))))
        self.assertIn(
            sum(TimeEntry.objects.filter(user=person).values_list('hours', flat=True)), (15, 18) if amend else (15,)
        )
        import_won = isinstance(results[0], dict)
        self.assertEqual(TimeEntry.objects.count() - baseline[0], 2 if amend and not import_won else 1)
        self.assertEqual(ActionReceipt.objects.count() - baseline[1], 2 if import_won else 1)
        self.assertEqual(AuditLog.objects.count() - baseline[2], 1)

    def test_time_import_and_single_time_serialize_daily_limit(self):
        self.daily_limit_race()

    def test_time_import_and_amendment_serialize_daily_limit(self):
        self.daily_limit_race(amend=True)

    def wait_on_person(self, person, action, while_waiting):
        ready, context = Event(), {}

        def worker():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '10s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    context['pid'] = cursor.fetchone()[0]
                ready.set()
                return action()
            except Exception as exc:
                return exc
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                User.objects.select_for_update(no_key=True).get(pk=person.pk)
                future = pool.submit(worker)
                self.assertTrue(ready.wait(5))
                self.wait_for_lock(context['pid'])
                while_waiting()
            return future.result(timeout=15)

    def test_time_person_wait_rechecks_actor_permission_before_writing(self):
        actor, person = self.users['manager'], self.users['member']
        task = Task.objects.create(project=self.first, title='撤权等待', kind='design', assignee=person)
        original = execution.log_time(
            actor,
            'revoke-original',
            task.pk,
            {
                'user': person.pk,
                'date': TODAY,
                'hours': '1',
                'reason': '原登记',
            },
        )
        for kind in ('import', 'single', 'amend'):
            with self.subTest(kind=kind):
                User.objects.filter(pk=actor.pk).update(role='manager')
                actor.refresh_from_db()
                token = self.time_preview(actor, task, person)
                if kind == 'import':

                    def action():
                        return transfers.confirm(actor, 'time', token)
                elif kind == 'single':

                    def action():
                        return execution.log_time(
                            actor,
                            'revoke-single',
                            task.pk,
                            {
                                'user': person.pk,
                                'date': TODAY,
                                'hours': '1',
                                'reason': '等待期间撤权',
                            },
                        )
                else:

                    def action():
                        return execution.amend_time(
                            actor,
                            'revoke-amend',
                            original['id'],
                            {
                                'date': TODAY,
                                'hours': '2',
                                'reason': '等待期间撤权',
                            },
                        )

                baseline = (TimeEntry.objects.count(), ActionReceipt.objects.count(), AuditLog.objects.count())
                result = self.wait_on_person(
                    person, action, lambda: User.objects.filter(pk=actor.pk).update(role='member')
                )
                self.assertIsInstance(result, PermissionDenied, repr(result))
                self.assertEqual(
                    (TimeEntry.objects.count(), ActionReceipt.objects.count(), AuditLog.objects.count()), baseline
                )

    def test_time_import_wait_reads_updated_person_rate(self):
        actor, person = self.users['manager'], self.users['member']
        task = Task.objects.create(project=self.first, title='费率等待', kind='design', assignee=person)
        token = self.time_preview(actor, task, person)
        result = self.wait_on_person(
            person,
            lambda: transfers.confirm(actor, 'time', token),
            lambda: User.objects.filter(pk=person.pk).update(hourly_cost='23.50'),
        )
        self.assertIsInstance(result, dict, repr(result))
        saved = TimeEntry.objects.get(pk=result['results'][0]['id'])
        self.assertEqual((saved.hourly_cost, saved.cost), (Decimal('23.50'), Decimal('23.50')))
