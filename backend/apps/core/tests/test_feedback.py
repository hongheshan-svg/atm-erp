import base64
import hashlib
import io
import urllib.error
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core import feedback
from apps.core.models import ActionReceipt, AuditLog, Company, Feedback
from apps.core.version import VERSION

TOKEN = 'github_pat_' + 'A1' * 20
ISSUE = {'number': 41, 'html_url': 'https://github.com/hongheshan-svg/atm-erp-feedback/issues/41'}
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
XLSX = b'PK\x03\x04' + b'\x00' * 32


def png(name='截图 [1].png', content=PNG):
    return SimpleUploadedFile(name, content, content_type='image/png')


class GitHubStub:
    """记录调用；PUT 附件按 put 结果返回，建 issue 返回 ISSUE。"""

    def __init__(self, put=None, get=None):
        self.calls, self.put, self.get = [], put or {'content': {}}, get

    def __call__(self, method, path, secret, data=None, **options):
        self.calls.append((method, path, secret, data))
        if method == 'PUT':
            return self.put
        if method == 'GET':
            return self.get
        return ISSUE

    def issue(self):
        return next(call for call in self.calls if call[:2] == ('POST', '/issues'))


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

    def fields(self, **changes):
        return {
            'category': 'bug',
            'title': '收货后  库存没有增加',
            'description': '采购收货后库存页数量不变',
            'steps': '1. 收货 2. 打开库存',
            'expected': '库存增加 10 件',
            'impact': 'blocked',
            'frequency': 'always',
            'page': '/inventory?section=stocks&search=某客户',
            'request_id': 'req-123',
            'client': 'Mozilla/5.0 | `x` · 390×844',
            **changes,
        }

    def submit(self, key='fb-1', **changes):
        return self.client.post('/api/core/feedback/', self.fields(**changes), format='json', HTTP_IDEMPOTENCY_KEY=key)

    def submit_files(self, files, key='fb-files', **changes):
        return self.client.post(
            '/api/core/feedback/',
            {**self.fields(**changes), 'files': files},
            format='multipart',
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_submit_creates_issue_without_submitter_and_records_locally(self):
        stub = GitHubStub()
        with patch('apps.core.feedback.github', side_effect=stub):
            response = self.submit()
        self.assertEqual(response.status_code, 200, response.data)
        method, path, secret, data = stub.issue()
        self.assertEqual(secret, TOKEN)
        self.assertEqual(data['title'], '收货后 库存没有增加')
        self.assertEqual(data['labels'], ['from-erp', 'bug'])
        body = data['body']
        for text in (
            f'v{VERSION}',
            '| 影响 | 无法继续工作 |',
            '| 频率 | 每次都出现 |',
            '`/inventory?section=stocks`',
            '`req-123`',
            'purchaser',
            '```text\n采购收货后库存页数量不变\n```',
            '### 期望结果\n\n```text\n库存增加 10 件\n```',
        ):
            self.assertIn(text, body)
        for private in ('fb-member', '采购员乙', '某客户', '| `x`', '### 附件'):
            self.assertNotIn(private, body)
        item = Feedback.objects.get()
        self.assertEqual(
            (item.issue_number, item.created_by, item.state, item.attachments), (41, self.member, 'open', [])
        )
        self.assertEqual(response.data['issue_url'], ISSUE['html_url'])
        self.assertTrue(response.data['mine'])
        self.assertEqual(AuditLog.objects.get(operation='feedback.submit').detail, {'issue': 41, 'attachments': 0})

    def test_user_text_is_fenced_so_markdown_and_mentions_render_as_text(self):
        stub = GitHubStub()
        with patch('apps.core.feedback.github', side_effect=stub):
            self.submit(description='@someone 看 ```代码``` 和 <img src=x>', steps='', expected='')
        body = stub.issue()[3]['body']
        self.assertIn('````text\n@someone 看 ```代码``` 和 <img src=x>\n````', body)
        self.assertNotIn('操作步骤', body)
        self.assertNotIn('期望结果', body)

    def test_attachments_are_uploaded_by_content_and_shown_in_issue(self):
        stub = GitHubStub()
        files = [png(), SimpleUploadedFile('导入_错误.XLSX', XLSX)]
        with patch('apps.core.feedback.github', side_effect=stub):
            response = self.submit_files(files)
        self.assertEqual(response.status_code, 200, response.data)
        puts = [call for call in stub.calls if call[0] == 'PUT']
        digest = hashlib.sha256(PNG).hexdigest()
        self.assertEqual(
            [(path, secret) for _, path, secret, _ in puts],
            [
                (f'/contents/files/{digest}.png', TOKEN),
                (f'/contents/files/{hashlib.sha256(XLSX).hexdigest()}.xlsx', TOKEN),
            ],
        )
        self.assertEqual(base64.b64decode(puts[0][3]['content']), PNG)
        image = f'{feedback.FILE_URL}{digest}.png?raw=true'
        body = stub.issue()[3]['body']
        self.assertIn(f'### 附件\n\n![截图 1.png]({image})', body)
        self.assertIn(f'- [导入\\_错误.xlsx]({feedback.FILE_URL}{hashlib.sha256(XLSX).hexdigest()}.xlsx)', body)
        self.assertEqual(response.data['attachments'][0], {'name': '截图 1.png', 'url': image, 'image': True})
        self.assertEqual(Feedback.objects.get().attachments[1]['image'], False)
        self.assertEqual(AuditLog.objects.get(operation='feedback.submit').detail['attachments'], 2)

    def test_existing_attachment_is_reused_and_unconfirmed_conflict_fails(self):
        with patch('apps.core.feedback.github', side_effect=GitHubStub(put={'_status': 422}, get={'sha': 'x'})):
            self.assertEqual(self.submit_files([png()], key='a').status_code, 200)
        with patch('apps.core.feedback.github', side_effect=GitHubStub(put={'_status': 422}, get={'_status': 404})):
            response = self.submit_files([png()], key='b')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(Feedback.objects.count(), 1)

    def test_attachments_are_validated_before_network(self):
        cases = (
            [png(content=b'GIF89a not a png')],
            [SimpleUploadedFile('tool.exe', b'MZ' + b'\x00' * 10)],
            [SimpleUploadedFile('page.svg', b'<svg onload=alert(1)>')],
            [SimpleUploadedFile('binary.txt', b'abc\x00def')],
            [png(f'{index}.png') for index in range(feedback.MAX_FILES + 1)],
        )
        with patch('apps.core.feedback.github') as github:
            for index, files in enumerate(cases):
                with self.subTest(index=index):
                    self.assertEqual(self.submit_files(files, key=f'bad-file-{index}').status_code, 400)
            with patch.object(feedback, 'MAX_FILE_MB', 0):
                self.assertEqual(self.submit_files([png()], key='too-big').status_code, 400)
        github.assert_not_called()

    def test_replay_with_attachments_does_not_reupload(self):
        stub = GitHubStub()
        with patch('apps.core.feedback.github', side_effect=stub):
            first = self.submit_files([png()], key='replay')
            second = self.submit_files([png()], key='replay')
            changed = self.submit_files([png(content=PNG + b'1')], key='replay')
        self.assertEqual(first.data, second.data)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual([call[0] for call in stub.calls], ['PUT', 'POST'])

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
            {'impact': 'urgent'},
            {'frequency': 'never'},
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
        self.assertEqual(response.data['limits'], {'files': 6, 'file_mb': 10, 'total_mb': 20})
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

        def save(token, key):
            return self.client.post(
                '/api/core/feedback/settings/', {'token': token}, format='json', HTTP_IDEMPOTENCY_KEY=key
            )

        with patch('apps.core.feedback.github', return_value={'full_name': 'x'}) as github:
            response = save(f' {new} ', 'cfg-1')
        self.assertEqual(response.status_code, 200, response.data)
        github.assert_called_once_with('GET', '', new)
        self.assertEqual(Company.objects.get(pk=1).feedback_token, new)
        self.assertNotIn(new, str(response.data) + str(self.client.get('/api/core/feedback/settings/').data))
        self.assertNotIn(new, str(list(ActionReceipt.objects.values())))
        self.assertEqual(AuditLog.objects.get(operation='feedback.configure').detail, {'configured': True})
        with patch('apps.core.feedback.github') as github:
            bad = save('ghs_short', 'cfg-2')
            extra = self.client.post(
                '/api/core/feedback/settings/',
                {'token': new, 'target': 'files'},
                format='json',
                HTTP_IDEMPOTENCY_KEY='cfg-3',
            )
            cleared = save('', 'cfg-4')
        github.assert_not_called()
        self.assertEqual((bad.status_code, extra.status_code), (400, 400))
        self.assertEqual(cleared.data, {'configured': False, 'repository': 'hongheshan-svg/atm-erp-feedback'})
        self.assertEqual(Company.objects.get(pk=1).feedback_token, '')

    def test_github_errors_become_chinese_messages(self):
        def error(code, headers=None):
            return urllib.error.HTTPError('u', code, 'x', headers or {}, io.BytesIO(b''))

        cases = (
            (error(401), '令牌无效或已过期'),
            (error(404), '没有反馈仓库的 Issues 和 Contents 读写权限'),
            (error(403), '没有反馈仓库的 Issues 和 Contents 读写权限'),
            (error(403, {'x-ratelimit-remaining': '0'}), '内容未提交'),
            (urllib.error.URLError('down'), '内容未提交'),
            (TimeoutError(), '内容未提交'),
        )
        for raised, text in cases:
            with self.subTest(raised=raised), patch('urllib.request.urlopen', side_effect=raised):
                with self.assertRaises(feedback.Unavailable) as caught:
                    feedback.github('GET', '', TOKEN)
                self.assertIn(text, str(caught.exception.detail))
        with patch('urllib.request.urlopen', side_effect=error(422)):
            self.assertEqual(feedback.github('PUT', '/x', TOKEN, {}, allow=(422,)), {'_status': 422})
