"""问题反馈：员工在 ERP 里提交问题和附件，服务端用管理员配置的 GitHub 令牌建成私有仓库的 issue。

问题与附件都放在单独的私有仓库，只有维护者能看到。令牌只授予该私有仓库的 Issues 与 Contents 读写，
即使服务器泄露也不能改动代码仓库；令牌只存服务端、任何接口都不回显。
issue 正文不写提交人；提交人与 issue 的对应关系记在本地反馈记录和操作审计里。
"""

import base64
import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.core.cache import cache
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .actions import perform, require_key
from .api import Conflict
from .models import ActionReceipt, AuditLog, Company, Feedback
from .permissions import ADMIN, ALL_ROLES, PermissionMixin, require_role, roles
from .version import VERSION

logger = logging.getLogger(__name__)
REPO = 'hongheshan-svg/atm-erp-feedback'
ISSUES_URL = f'https://github.com/{REPO}/issues'
# 私有仓库的文件页；图片加 ?raw=true，已登录且有权限的维护者在 issue 里能直接看到。
FILE_URL = f'https://github.com/{REPO}/blob/main/files/'
LABEL = 'from-erp'
# 类型 → (页面显示, GitHub 默认标签)
CATEGORIES = {'bug': ('错误', 'bug'), 'feature': ('功能建议', 'enhancement'), 'question': ('使用问题', 'question')}
IMPACTS = {'blocked': '无法继续工作', 'workaround': '有替代办法', 'minor': '轻微不便'}
FREQUENCIES = {'always': '每次都出现', 'sometimes': '偶尔出现', 'once': '只出现过一次'}
FIELDS = {
    'category',
    'title',
    'description',
    'steps',
    'expected',
    'impact',
    'frequency',
    'page',
    'request_id',
    'client',
}
TOKEN = re.compile(r'(github_pat_|ghp_)[A-Za-z0-9_]{20,250}')
REQUEST_ID = re.compile(r'[A-Za-z0-9._-]{1,64}')
PATH = re.compile(r'/[A-Za-z0-9/_-]{0,100}')
QUERY_KEYS = ('resource', 'section')
QUERY_VALUE = re.compile(r'[a-z0-9-]{1,40}')
SYNC_CACHE = 'feedback.sync'
SYNC_SECONDS = 120
MAX_FILES = 6
MAX_FILE_MB = 10
MAX_TOTAL_MB = 20
# 只收被动格式并核对文件头；图片在 issue 里直接显示，其余给下载链接。不收 HTML、SVG 和可执行文件。
IMAGES = {
    '.png': lambda c: c.startswith(b'\x89PNG\r\n\x1a\n'),
    '.jpg': lambda c: c.startswith(b'\xff\xd8\xff'),
    '.jpeg': lambda c: c.startswith(b'\xff\xd8\xff'),
    '.gif': lambda c: c.startswith((b'GIF87a', b'GIF89a')),
    '.webp': lambda c: c.startswith(b'RIFF') and c[8:12] == b'WEBP',
}
DOCUMENTS = {
    '.pdf': lambda c: c.startswith(b'%PDF-'),
    '.xlsx': lambda c: c.startswith(b'PK\x03\x04'),
    '.docx': lambda c: c.startswith(b'PK\x03\x04'),
    '.xls': lambda c: c.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
    '.mp4': lambda c: c[4:8] == b'ftyp',
    '.mov': lambda c: c[4:8] in (b'ftyp', b'moov', b'wide', b'mdat', b'free'),
    **{ext: (lambda c: b'\x00' not in c[:65536]) for ext in ('.txt', '.log', '.csv', '.json')},
}
KINDS = '图片 png/jpg/gif/webp，文件 pdf/xlsx/xls/docx/csv/txt/log/json，录屏 mp4/mov'


class Unavailable(APIException):
    status_code = 503
    default_detail = '暂时无法连接 GitHub，内容未提交，请稍后重试。'


class FeedbackThrottle(UserRateThrottle):
    """每次提交都在反馈仓库建一个 issue；限流防的是脚本失控或连点刷屏。"""

    scope = 'feedback'


def token():
    return Company.objects.filter(pk=1).values_list('feedback_token', flat=True).first() or ''


def github(method, path, secret, data=None, *, allow=(), timeout=20):
    """调用 GitHub REST API。allow 中的状态码返回 {'_status': code}，其余错误转为中文提示。"""
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode()
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {secret}',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'Lean-ERP-feedback',
    }
    if body is not None:
        headers['Content-Type'] = 'application/json'
    url = f'https://api.github.com/repos/{REPO}{path}'
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
    except urllib.error.HTTPError as exc:
        if exc.code in allow:
            return {'_status': exc.code}
        limited = exc.headers.get('x-ratelimit-remaining') == '0' if exc.headers else False
        # 原因只进日志和提示里的状态码；不记录请求头和返回内容，避免带出令牌或反馈原文。
        logger.warning('问题反馈调用 GitHub 失败：%s %s 返回 %s', method, url, exc.code)
        if exc.code == 401:
            raise Unavailable('问题反馈的 GitHub 令牌无效或已过期，请管理员在「问题反馈」页更新。') from exc
        if exc.code in (403, 404) and not limited:
            raise Unavailable(
                '问题反馈的 GitHub 令牌没有反馈仓库的 Issues 和 Contents 读写权限，请管理员在「问题反馈」页更换。'
            ) from exc
        if limited or exc.code == 429:
            raise Unavailable('GitHub 接口调用次数已达上限，内容未提交，请稍后重试。') from exc
        raise Unavailable(f'GitHub 返回错误（{exc.code}），内容未提交，请稍后重试。') from exc
    except OSError as exc:
        logger.warning('问题反馈无法连接 GitHub：%s %s：%r', method, url, exc)
        if isinstance(exc, TimeoutError) or isinstance(getattr(exc, 'reason', None), TimeoutError):
            # 超时可能发生在 GitHub 已收到请求之后，不能断言没有提交。
            raise Unavailable(
                '连接 GitHub 超时，请稍后刷新列表确认后再重试；多次超时请管理员检查服务器到 api.github.com 的网络。'
            ) from exc
        raise Unavailable() from exc
    try:
        if len(raw) > 2_000_000:
            raise ValueError('返回内容过大')
        return json.loads(raw)
    except ValueError as exc:
        logger.warning('问题反馈收到无法解析的 GitHub 返回：%s %s：%r', method, url, exc)
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


def choice(data, key, label, options):
    value = data.get(key) or ''
    if value and value not in options:
        raise ValidationError({key: f'请选择有效的{label}。'})
    return value


def page(value):
    """只保留路径和定位用的 resource/section 参数；搜索词、筛选条件可能含客户名称，不写进 issue。"""
    if not isinstance(value, str) or len(value) > 500:
        return ''
    parts = urlsplit(value)
    if not PATH.fullmatch(parts.path):
        return ''
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in QUERY_KEYS and QUERY_VALUE.fullmatch(v)]
    return parts.path + (f'?{urlencode(query)}' if query else '')


def clean(data):
    if hasattr(data, 'lists'):
        # multipart 表单：每个文字字段只取一个值，重复提交同名字段视为格式错误。
        if any(len(values) > 1 for _, values in data.lists()):
            raise ValidationError('提交内容格式不正确，请刷新页面后重试。')
        data = {key: data.get(key) for key in data}
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
        'steps': text(data, 'steps', '操作步骤', 3000, required=False),
        'expected': text(data, 'expected', '期望结果', 2000, required=False),
        'impact': choice(data, 'impact', '影响程度', IMPACTS),
        'frequency': choice(data, 'frequency', '出现频率', FREQUENCIES),
        'page': page(data.get('page')),
        'request_id': request_id,
        # 进表格单元格和行内代码，去掉会破坏格式的竖线与反引号。
        'client': ' '.join(re.sub(r'[|`]', ' ', text(data, 'client', '浏览器信息', 300, required=False)).split()),
    }


def display_name(name, index):
    path = Path(str(name or ''))
    stem = ' '.join(re.sub(r'[\x00-\x1f\[\]()<>|`\\]', ' ', path.stem).split())[:60]
    return (stem or f'附件{index}') + path.suffix.lower()


def read_files(request):
    if set(request.FILES) - {'files'}:
        raise ValidationError('附件格式不正确，请刷新页面后重试。')
    uploads = request.FILES.getlist('files')
    if len(uploads) > MAX_FILES:
        raise ValidationError({'files': f'一次最多上传 {MAX_FILES} 个附件。'})
    files, total = [], 0
    for index, upload in enumerate(uploads, 1):
        name = display_name(upload.name, index)
        extension = Path(name).suffix
        check = IMAGES.get(extension) or DOCUMENTS.get(extension)
        if not check:
            raise ValidationError({'files': f'「{name}」的格式不支持。支持{KINDS}。'})
        total += upload.size
        if upload.size > MAX_FILE_MB * 1024 * 1024 or total > MAX_TOTAL_MB * 1024 * 1024:
            raise ValidationError({'files': f'单个附件不能超过 {MAX_FILE_MB} MB，合计不能超过 {MAX_TOTAL_MB} MB。'})
        content = upload.read()
        if not content or not check(content):
            raise ValidationError({'files': f'「{name}」的内容与扩展名不一致或文件已损坏。'})
        digest = hashlib.sha256(content).hexdigest()
        files.append({'name': name, 'path': digest + extension, 'image': extension in IMAGES, 'content': content})
    return files


def upload(secret, item):
    """按内容摘要命名上传到反馈仓库的 files/；同一文件已存在时直接复用。"""
    path = f'/contents/files/{item["path"]}'
    body = {'message': f'问题反馈附件 {item["path"][:12]}', 'content': base64.b64encode(item['content']).decode()}
    for _ in range(3):
        result = github('PUT', path, secret, body, allow=(409, 422), timeout=120)
        status = result.get('_status') if isinstance(result, dict) else None
        if status is None:
            return
        if status == 422:
            # 路径已存在时 GitHub 要求带旧版本摘要；路径就是内容摘要，存在即同一文件。
            existing = github('GET', path, secret, allow=(404,))
            if '_status' not in existing:
                return
            break
        # 409：同时有其他提交写入反馈仓库，重试。
    raise Unavailable('附件上传失败，内容未提交，请稍后重试。')


def attachment(item):
    return {
        'name': item['name'],
        'url': FILE_URL + item['path'] + ('?raw=true' if item['image'] else ''),
        'image': item['image'],
    }


def markdown_text(value):
    return re.sub(r'([*_~#!])', r'\\\1', value)


def block(value):
    """用户原文放进足够长的代码围栏：@提及、链接、图片和 HTML 都按纯文本显示。"""
    fence = '`' * max(3, max((len(run) for run in re.findall(r'`+', value)), default=0) + 1)
    return f'{fence}text\n{value}\n{fence}'


def issue_body(values, actor, attachments=()):
    rows = [('类型', CATEGORIES[values['category']][0])]
    if values['impact']:
        rows.append(('影响', IMPACTS[values['impact']]))
    if values['frequency']:
        rows.append(('频率', FREQUENCIES[values['frequency']]))
    rows += [('版本', f'v{VERSION}'), ('提交人岗位', '、'.join(sorted(roles(actor))) or '-')]
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
    for key, title in (('steps', '操作步骤'), ('expected', '期望结果')):
        if values[key]:
            lines += ['', f'### {title}', '', block(values[key])]
    if attachments:
        lines += ['', '### 附件', '']
        for item in attachments:
            name = markdown_text(item['name'])
            lines += [f'![{name}]({item["url"]})', ''] if item['image'] else [f'- [{name}]({item["url"]})']
    return '\n'.join(lines).rstrip('\n') + '\n'


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
        'attachments': item.attachments,
        'submitter': item.created_by.display_name or item.created_by.username if item.created_by else '',
        'mine': item.created_by_id == viewer.pk,
        'created_at': item.created_at.isoformat(),
    }


class FeedbackView(APIView):
    """所有在职员工都能提交和查看反馈列表；GitHub 上的 issue 与附件只有维护者能看到。"""

    parser_classes = [JSONParser, MultiPartParser]

    def get_throttles(self):
        return [FeedbackThrottle()] if self.request.method == 'POST' else super().get_throttles()

    def get(self, request):
        require_role(request.user, ALL_ROLES)
        secret = token()
        sync(secret)
        items = Feedback.objects.select_related('created_by')[:100]
        return Response(
            {
                'enabled': bool(secret),
                'limits': {'files': MAX_FILES, 'file_mb': MAX_FILE_MB, 'total_mb': MAX_TOTAL_MB},
                'issues_url': ISSUES_URL,
                'results': [row(item, request.user) for item in items],
            }
        )

    def post(self, request):
        require_role(request.user, ALL_ROLES)
        # multipart 的 request.data 混有文件，文字字段从 request.POST 取；JSON 提交没有附件。
        values = clean(request.POST if hasattr(request.data, 'lists') else request.data)
        files = read_files(request)
        key = require_key(request.headers.get('Idempotency-Key'))
        issue, attachments = None, [attachment(item) for item in files]
        # 同一操作标识的并发重试在建 issue 之前互斥，回执落库后才放开，避免建出两个相同 issue。
        lock = f'feedback.submit.{request.user.pk}.{hashlib.sha256(key.encode()).hexdigest()}'
        locked = False
        try:
            # 已完成的请求重放时不再访问 GitHub；结果、指纹与授权仍由 perform 锁内核验。
            if not ActionReceipt.objects.filter(actor=request.user, key=key).exists():
                secret = token()
                if not secret:
                    raise Conflict('管理员尚未配置问题反馈的 GitHub 连接，暂时无法提交。')
                locked = cache.add(lock, True, 300)
                if not locked:
                    raise Conflict('这条反馈正在提交，请稍后刷新列表查看。')
                for item in files:
                    upload(secret, item)
                created = github(
                    'POST',
                    '/issues',
                    secret,
                    {
                        'title': values['title'],
                        'body': issue_body(values, request.user, attachments),
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
                    attachments=attachments,
                    created_by=actor,
                    updated_by=actor,
                )
                AuditLog.objects.create(
                    actor=actor,
                    operation='feedback.submit',
                    resource=f'feedback:{item.pk}',
                    detail={'issue': item.issue_number, 'attachments': len(attachments)},
                )
                return row(item, actor)

            return Response(
                perform(
                    actor=request.user,
                    key=key,
                    operation='feedback.submit',
                    payload={**values, 'files': [[item['path'], item['name']] for item in files]},
                    authorize=lambda actor: require_role(actor, ALL_ROLES),
                    execute=execute,
                )
            )
        finally:
            if locked:
                cache.delete(lock)


def settings_data():
    return {'configured': bool(token()), 'repository': REPO}


class FeedbackSettingsView(PermissionMixin, APIView):
    read_roles = write_roles = ADMIN

    def get(self, request):
        return Response(settings_data())

    def post(self, request):
        payload = request.data
        if not isinstance(payload, dict) or set(payload) != {'token'} or not isinstance(payload['token'], str):
            raise ValidationError('请提交 GitHub 令牌；留空表示停用问题反馈。')
        secret = payload['token'].strip()
        if secret and not TOKEN.fullmatch(secret):
            raise ValidationError({'token': '令牌格式不正确，请粘贴以 github_pat_ 开头的细粒度令牌。'})
        key = require_key(request.headers.get('Idempotency-Key'))
        if secret and not ActionReceipt.objects.filter(actor=request.user, key=key).exists():
            github('GET', '', secret)  # 保存前确认令牌有效、能访问反馈仓库。

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
            return settings_data()

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
