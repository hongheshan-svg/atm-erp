"""问题反馈：员工在 ERP 里提交问题，服务端用管理员配置的 GitHub 令牌建成公开 issue。

令牌只存服务端、任何接口都不回显。issue 公开可见，正文只写类型、版本、页面路径、岗位和错误编号，
不写提交人；提交人与 issue 的对应关系记在本地反馈记录和操作审计里。
"""

import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.core.cache import cache
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .actions import perform, require_key
from .api import Conflict
from .models import ActionReceipt, AuditLog, Company, Feedback
from .ota import REPO
from .permissions import ADMIN, ALL_ROLES, PermissionMixin, require_role, roles
from .version import VERSION

logger = logging.getLogger(__name__)
API = f'https://api.github.com/repos/{REPO}'
ISSUES_URL = f'https://github.com/{REPO}/issues'
LABEL = 'from-erp'
# 类型 → (页面显示, GitHub 默认标签)
CATEGORIES = {'bug': ('错误', 'bug'), 'feature': ('功能建议', 'enhancement'), 'question': ('使用问题', 'question')}
FIELDS = {'category', 'title', 'description', 'steps', 'page', 'request_id', 'client'}
TOKEN = re.compile(r'(github_pat_|ghp_)[A-Za-z0-9_]{20,250}')
REQUEST_ID = re.compile(r'[A-Za-z0-9._-]{1,64}')
PATH = re.compile(r'/[A-Za-z0-9/_-]{0,100}')
QUERY_KEYS = ('resource', 'section')
QUERY_VALUE = re.compile(r'[a-z0-9-]{1,40}')
SYNC_CACHE = 'feedback.sync'
SYNC_SECONDS = 120


class Unavailable(APIException):
    status_code = 503
    default_detail = '暂时无法连接 GitHub，内容未提交，请稍后重试。'


class FeedbackThrottle(UserRateThrottle):
    """每次提交都在公开仓库建一个 issue；限流防的是脚本失控或连点刷屏。"""

    scope = 'feedback'


def token():
    return Company.objects.filter(pk=1).values_list('feedback_token', flat=True).first() or ''


def github(method, path, secret, data=None):
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode()
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {secret}',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'Lean-ERP-feedback',
    }
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(API + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read(2_000_001)
    except urllib.error.HTTPError as exc:
        limited = exc.headers.get('x-ratelimit-remaining') == '0' if exc.headers else False
        if exc.code == 401:
            raise Unavailable('GitHub 令牌无效或已过期，请管理员在「问题反馈」页更新令牌。') from exc
        if exc.code in (403, 404) and not limited:
            raise Unavailable('GitHub 令牌没有该仓库的 Issues 读写权限，请管理员在「问题反馈」页更换令牌。') from exc
        raise Unavailable() from exc
    except OSError as exc:
        raise Unavailable() from exc
    try:
        if len(raw) > 2_000_000:
            raise ValueError('返回内容过大')
        return json.loads(raw)
    except ValueError as exc:
        raise Unavailable() from exc


def text(data, key, label, limit, required=True):
    value = data.get(key, '')
    if not isinstance(value, str):
        raise ValidationError({key: f'{label}必须是文字。'})
    value = value.strip()
    if required and not value:
        raise ValidationError({key: f'请填写{label}。'})
    if len(value) > limit:
        raise ValidationError({key: f'{label}不能超过 {limit} 个字符。'})
    return value


def page(value):
    """只保留路径和定位用的 resource/section 参数；搜索词、筛选条件可能含客户名称，不写进公开 issue。"""
    if not isinstance(value, str) or len(value) > 500:
        return ''
    parts = urlsplit(value)
    if not PATH.fullmatch(parts.path):
        return ''
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in QUERY_KEYS and QUERY_VALUE.fullmatch(v)]
    return parts.path + (f'?{urlencode(query)}' if query else '')


def clean(data):
    if not isinstance(data, dict) or not set(data) <= FIELDS:
        raise ValidationError('提交内容格式不正确，请刷新页面后重试。')
    if data.get('category') not in CATEGORIES:
        raise ValidationError({'category': '请选择问题类型。'})
    request_id = text(data, 'request_id', '错误编号', 64, required=False)
    if request_id and not REQUEST_ID.fullmatch(request_id):
        raise ValidationError({'request_id': '错误编号格式不正确，请从错误提示里原样复制。'})
    return {
        'category': data['category'],
        'title': ' '.join(text(data, 'title', '标题', 80).split()),
        'description': text(data, 'description', '问题描述', 5000),
        'steps': text(data, 'steps', '复现步骤', 3000, required=False),
        'page': page(data.get('page')),
        'request_id': request_id,
        # 进表格单元格和行内代码，去掉会破坏格式的竖线与反引号。
        'client': ' '.join(re.sub(r'[|`]', ' ', text(data, 'client', '浏览器信息', 300, required=False)).split()),
    }


def block(value):
    """用户原文放进足够长的代码围栏：@提及、链接、图片和 HTML 都按纯文本显示。"""
    fence = '`' * max(3, max((len(run) for run in re.findall(r'`+', value)), default=0) + 1)
    return f'{fence}text\n{value}\n{fence}'


def issue_body(values, actor):
    rows = [
        ('类型', CATEGORIES[values['category']][0]),
        ('版本', f'v{VERSION}'),
        ('提交人岗位', '、'.join(sorted(roles(actor))) or '-'),
    ]
    rows += [
        (label, f'`{values[key]}`')
        for key, label in (('page', '页面'), ('request_id', '错误编号'), ('client', '浏览器'))
        if values[key]
    ]
    lines = [
        '由 Lean ERP 内的「问题反馈」页面提交；提交人只记录在该安装的操作审计中。',
        '',
        '| 项目 | 内容 |',
        '| --- | --- |',
    ]
    lines += [f'| {label} | {value} |' for label, value in rows]
    lines += ['', '### 问题描述', '', block(values['description'])]
    if values['steps']:
        lines += ['', '### 复现步骤与期望结果', '', block(values['steps'])]
    return '\n'.join(lines) + '\n'


def state_of(issue):
    if issue.get('state') == 'open':
        return 'open'
    return 'not_planned' if issue.get('state_reason') in ('not_planned', 'duplicate') else 'completed'


def sync(secret):
    """全安装每两分钟最多向 GitHub 取一次状态；失败只记日志，列表照常返回上次状态。"""
    if not secret or not Feedback.objects.exists() or not cache.add(SYNC_CACHE, True, SYNC_SECONDS):
        return
    try:
        issues = github('GET', f'/issues?labels={LABEL}&state=all&sort=updated&direction=desc&per_page=100', secret)
    except Unavailable:
        logger.warning('问题反馈状态同步失败', exc_info=True)
        return
    for issue in issues if isinstance(issues, list) else []:
        if isinstance(issue, dict) and type(issue.get('number')) is int and 'pull_request' not in issue:
            Feedback.objects.filter(issue_number=issue['number']).exclude(state=state_of(issue)).update(
                state=state_of(issue)
            )


def row(item, viewer):
    return {
        'id': item.pk,
        'category': item.category,
        'title': item.title,
        'issue_number': item.issue_number,
        'issue_url': item.issue_url,
        'state': item.state,
        'submitter': item.created_by.display_name or item.created_by.username if item.created_by else '',
        'mine': item.created_by_id == viewer.pk,
        'created_at': item.created_at.isoformat(),
    }


class FeedbackView(APIView):
    """所有在职员工都能提交和查看反馈；问题公开在 GitHub，本地列表只多一列提交人。"""

    def get_throttles(self):
        return [FeedbackThrottle()] if self.request.method == 'POST' else super().get_throttles()

    def get(self, request):
        require_role(request.user, ALL_ROLES)
        secret = token()
        sync(secret)
        items = Feedback.objects.select_related('created_by')[:100]
        return Response(
            {'enabled': bool(secret), 'issues_url': ISSUES_URL, 'results': [row(item, request.user) for item in items]}
        )

    def post(self, request):
        require_role(request.user, ALL_ROLES)
        values = clean(request.data)
        key = require_key(request.headers.get('Idempotency-Key'))
        issue = None
        # 同一操作标识的并发重试在建 issue 之前互斥，回执落库后才放开，避免建出两个相同 issue。
        lock = f'feedback.submit.{request.user.pk}.{hashlib.sha256(key.encode()).hexdigest()}'
        locked = False
        try:
            # 已完成的请求重放时不再访问 GitHub；结果、指纹与授权仍由 perform 锁内核验。
            if not ActionReceipt.objects.filter(actor=request.user, key=key).exists():
                secret = token()
                if not secret:
                    raise Conflict('管理员尚未配置问题反馈的 GitHub 连接，暂时无法提交。')
                locked = cache.add(lock, True, 60)
                if not locked:
                    raise Conflict('这条反馈正在提交，请稍后刷新列表查看。')
                created = github(
                    'POST',
                    '/issues',
                    secret,
                    {
                        'title': values['title'],
                        'body': issue_body(values, request.user),
                        'labels': [LABEL, CATEGORIES[values['category']][1]],
                    },
                )
                number = created.get('number') if isinstance(created, dict) else None
                url = created.get('html_url') if isinstance(created, dict) else None
                if type(number) is not int or url != f'{ISSUES_URL}/{number}':
                    raise Unavailable('GitHub 返回内容异常，请到仓库 Issues 页确认是否已提交。')
                issue = {'number': number, 'url': url}

            def execute(actor):
                if issue is None:
                    raise Conflict('反馈记录已变化，请刷新列表查看。')
                item = Feedback.objects.create(
                    category=values['category'],
                    title=values['title'],
                    issue_number=issue['number'],
                    issue_url=issue['url'],
                    created_by=actor,
                    updated_by=actor,
                )
                AuditLog.objects.create(
                    actor=actor,
                    operation='feedback.submit',
                    resource=f'feedback:{item.pk}',
                    detail={'issue': item.issue_number},
                )
                return row(item, actor)

            return Response(
                perform(
                    actor=request.user,
                    key=key,
                    operation='feedback.submit',
                    payload=values,
                    authorize=lambda actor: require_role(actor, ALL_ROLES),
                    execute=execute,
                )
            )
        finally:
            if locked:
                cache.delete(lock)


class FeedbackSettingsView(PermissionMixin, APIView):
    read_roles = write_roles = ADMIN

    def get(self, request):
        return Response({'configured': bool(token()), 'repository': REPO})

    def post(self, request):
        payload = request.data
        if not isinstance(payload, dict) or set(payload) != {'token'} or not isinstance(payload['token'], str):
            raise ValidationError('请提交 GitHub 令牌；留空表示停用问题反馈。')
        secret = payload['token'].strip()
        if secret and not TOKEN.fullmatch(secret):
            raise ValidationError({'token': '令牌格式不正确，请粘贴以 github_pat_ 开头的细粒度令牌。'})
        key = require_key(request.headers.get('Idempotency-Key'))
        if secret and not ActionReceipt.objects.filter(actor=request.user, key=key).exists():
            github('GET', '', secret)  # 保存前确认令牌有效、能访问该仓库。

        def execute(actor):
            company = Company.objects.select_for_update().filter(pk=1).first()
            if not company:
                raise ValidationError('公司资料尚未初始化，请先完成启用指南。')
            company.feedback_token = secret
            company.save(update_fields=['feedback_token'])
            AuditLog.objects.create(
                actor=actor, operation='feedback.configure', resource='company:1', detail={'configured': bool(secret)}
            )
            cache.delete(SYNC_CACHE)
            return {'configured': bool(secret), 'repository': REPO}

        return Response(
            perform(
                actor=request.user,
                key=key,
                operation='feedback.configure',
                # 回执只留指纹；令牌先加盐摘要，回执表里查不到可比对的原值。
                payload={'token': salted_hmac('feedback-token', secret).hexdigest() if secret else ''},
                authorize=lambda actor: require_role(actor, ADMIN),
                execute=execute,
            )
        )
