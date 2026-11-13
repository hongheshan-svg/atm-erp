import io
import urllib.error
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core import feedback
from apps.core.models import ActionReceipt, AuditLog, Company, Feedback
from apps.core.version import VERSION

TOKEN = 'github_pat_' + 'A1' * 20
ISSUE = {'number': 41, 'html_url': 'https://github.com/hongheshan-svg/atm-erp/issues/41'}


class FeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        Company.objects.create(pk=1, feedback_token=TOKEN)
        self.admin = User.objects.create_user(
            username='fb-admin', password='test', role='admin', display_name='管理员甲'
        )
        self.member = User.objects.create_user(
            username='fb-member', password='test', role='purchaser', display_name='采购员乙'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.member)

    def submit(self, key='fb-1', **changes):
        data = {
            'category': 'bug',
            'title': '收货后  库存没有增加',
            'description': '采购收货后库存页数量不变',
            'steps': '1. 收货 2. 打开库存',
            'page': '/inventory?section=stocks&search=某客户',
            'request_id': 'req-123',
            'client': 'Mozilla/5.0 | `x` · 390×844',
            **changes,
        }
        return self.client.post('/api/core/feedback/', data, format='json', HTTP_IDEMPOTENCY_KEY=key)

    def test_submit_creates_public_issue_without_submitter_and_records_locally(self):
        with patch('apps.core.feedback.github', return_value=ISSUE) as github:
            response = self.submit()
        self.assertEqual(response.status_code, 200, response.data)
        method, path, secret, data = github.call_args.args
        self.assertEqual((method, path, secret), ('POST', '/issues', TOKEN))
        self.assertEqual(data['title'], '收货后 库存没有增加')
        self.assertEqual(data['labels'], ['from-erp', 'bug'])
        body = data['body']
        for text in (
            f'v{VERSION}',
            '`/inventory?section=stocks`',
            '`req-123`',
            'purchaser',
            '```text\n采购收货后库存页数量不变\n```',
        ):
            self.assertIn(text, body)
        for private in ('fb-member', '采购员乙', '某客户', '| `x`'):
            self.assertNotIn(private, body)
        item = Feedback.objects.get()
        self.assertEqual((item.issue_number, item.created_by, item.state), (41, self.member, 'open'))
        self.assertEqual(response.data['issue_url'], ISSUE['html_url'])
        self.assertTrue(response.data['mine'])
        self.assertEqual(AuditLog.objects.get(operation='feedback.submit').detail, {'issue': 41})

    def test_user_text_is_fenced_so_markdown_and_mentions_render_as_text(self):
        with patch('apps.core.feedback.github', return_value=ISSUE) as github:
            self.submit(description='@someone 看 ```代码``` 和 <img src=x>', steps='')
        body = github.call_args.args[3]['body']
        self.assertIn('````text\n@someone 看 ```代码``` 和 <img src=x>\n````', body)
        self.assertNotIn('复现步骤', body)

    def test_page_keeps_only_path_and_locator_parameters(self):
        self.assertEqual(
            feedback.page('/purchases?resource=purchases&search=客户A&focus=3'), '/purchases?resource=purchases'
        )
        self.assertEqual(feedback.page('/projects/12'), '/projects/12')
        for value in ('https://example.com/x', 'javascript:alert(1)', '/a b', None, '/x?resource=Bad Value'):
            self.assertIn(feedback.page(value), ('', '/x'))

    def test_retry_with_same_key_replays_without_second_issue(self):
        with patch('apps.core.feedback.github', return_value=ISSUE) as github:
            first = self.submit()
            second = self.submit()
        self.assertEqual(github.call_count, 1)
        self.assertEqual(first.data, second.data)
        self.assertEqual(Feedback.objects.count(), 1)

    def test_without_token_or_on_github_failure_nothing_is_recorded_and_retry_works(self):
        Company.objects.filter(pk=1).update(feedback_token='')
        with patch('apps.core.feedback.github') as github:
            self.assertEqual(self.submit().status_code, 409)
        github.assert_not_called()
        Company.objects.filter(pk=1).update(feedback_token=TOKEN)
        with patch('apps.core.feedback.github', side_effect=feedback.Unavailable()):
            response = self.submit()
        self.assertEqual(response.status_code, 503)
        self.assertIn('内容未提交', response.data['detail'])
        self.assertFalse(Feedback.objects.exists() or ActionReceipt.objects.exists())
        with patch('apps.core.feedback.github', return_value=ISSUE):
            self.assertEqual(self.submit().status_code, 200)

    def test_unexpected_github_response_is_not_recorded(self):
        with patch('apps.core.feedback.github', return_value={'number': 41, 'html_url': 'https://evil.example/41'}):
            self.assertEqual(self.submit().status_code, 503)
        self.assertFalse(Feedback.objects.exists())

    def test_invalid_submissions_are_rejected_before_network(self):
        cases = (
            {'title': '  '},
            {'description': ''},
            {'category': 'other'},
            {'request_id': '含 空格'},
            {'title': 'x' * 81},
            {'extra': 1},
        )
        with patch('apps.core.feedback.github') as github:
            for index, change in enumerate(cases):
                with self.subTest(change=change):
                    self.assertEqual(self.submit(key=f'bad-{index}', **change).status_code, 400)
            response = self.client.post(
                '/api/core/feedback/', {'category': 'bug', 'title': 't', 'description': 'd'}, format='json'
            )
            self.assertEqual(response.status_code, 400)
        github.assert_not_called()

    def test_submissions_are_throttled_per_user(self):
        with (
            patch.object(feedback.FeedbackThrottle, 'THROTTLE_RATES', {'feedback': '1/hour'}),
            patch('apps.core.feedback.github', return_value=ISSUE),
        ):
            self.assertEqual(self.submit(key='t-1').status_code, 200)
            self.assertEqual(self.submit(key='t-2').status_code, 429)
            self.assertEqual(self.client.get('/api/core/feedback/').status_code, 200)

    def test_list_shows_everyone_and_syncs_states_at_most_once_per_interval(self):
        Feedback.objects.create(category='bug', title='甲', issue_number=5, issue_url='u5', created_by=self.admin)
        Feedback.objects.create(category='feature', title='乙', issue_number=6, issue_url='u6', created_by=self.member)
        Feedback.objects.create(category='question', title='丙', issue_number=7, issue_url='u7', created_by=self.member)
        issues = [
            {'number': 5, 'state': 'closed', 'state_reason': 'completed'},
            {'number': 6, 'state': 'closed', 'state_reason': 'not_planned'},
            {'number': 7, 'state': 'open', 'pull_request': {}},
        ]
        with patch('apps.core.feedback.github', return_value=issues) as github:
            response = self.client.get('/api/core/feedback/')
            self.client.get('/api/core/feedback/')
        self.assertEqual(github.call_count, 1)
        self.assertEqual(
            github.call_args.args[:2],
            ('GET', '/issues?labels=from-erp&state=all&sort=updated&direction=desc&per_page=100'),
        )
        self.assertTrue(response.data['enabled'])
        rows = {row['issue_number']: row for row in response.data['results']}
        self.assertEqual({n: r['state'] for n, r in rows.items()}, {5: 'completed', 6: 'not_planned', 7: 'open'})
        self.assertEqual((rows[5]['submitter'], rows[5]['mine'], rows[6]['mine']), ('管理员甲', False, True))

    def test_sync_failure_keeps_last_known_state(self):
        Feedback.objects.create(category='bug', title='甲', issue_number=5, issue_url='u5', created_by=self.member)
        with patch('apps.core.feedback.github', side_effect=feedback.Unavailable()):
            response = self.client.get('/api/core/feedback/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['state'], 'open')

    def test_token_settings_are_admin_only_verified_and_never_echoed(self):
        self.assertEqual(self.client.get('/api/core/feedback/settings/').status_code, 403)
        self.client.force_authenticate(self.admin)
        new = 'github_pat_' + 'B2' * 20
        with patch('apps.core.feedback.github', return_value={'full_name': 'x'}) as github:
            response = self.client.post(
                '/api/core/feedback/settings/', {'token': f' {new} '}, format='json', HTTP_IDEMPOTENCY_KEY='cfg-1'
            )
        self.assertEqual(response.status_code, 200, response.data)
        github.assert_called_once_with('GET', '', new)
        self.assertEqual(Company.objects.get(pk=1).feedback_token, new)
        self.assertNotIn(new, str(response.data) + str(self.client.get('/api/core/feedback/settings/').data))
        self.assertNotIn(new, str(list(ActionReceipt.objects.values())))
        self.assertEqual(AuditLog.objects.get(operation='feedback.configure').detail, {'configured': True})
        with patch('apps.core.feedback.github') as github:
            bad = self.client.post(
                '/api/core/feedback/settings/', {'token': 'ghs_short'}, format='json', HTTP_IDEMPOTENCY_KEY='cfg-2'
            )
            cleared = self.client.post(
                '/api/core/feedback/settings/', {'token': ''}, format='json', HTTP_IDEMPOTENCY_KEY='cfg-3'
            )
        github.assert_not_called()
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(cleared.data, {'configured': False, 'repository': feedback.REPO})
        self.assertEqual(Company.objects.get(pk=1).feedback_token, '')

    def test_github_errors_become_chinese_messages(self):
        def error(code, headers=None):
            return urllib.error.HTTPError('u', code, 'x', headers or {}, io.BytesIO(b''))

        cases = (
            (error(401), '无效或已过期'),
            (error(404), '没有该仓库的 Issues 读写权限'),
            (error(403, {'x-ratelimit-remaining': '0'}), '内容未提交'),
            (urllib.error.URLError('down'), '内容未提交'),
            (TimeoutError(), '内容未提交'),
        )
        for raised, text in cases:
            with self.subTest(raised=raised), patch('urllib.request.urlopen', side_effect=raised):
                with self.assertRaises(feedback.Unavailable) as caught:
                    feedback.github('GET', '', TOKEN)
                self.assertIn(text, str(caught.exception.detail))
