import hashlib
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.permissions import ALL_ROLES, FINANCE, MANAGERS, MONEY_READERS, require_role, role

from ..models import Document
from .common import audit, identity, project_action, save

MAX_BYTES = 20 * 1024 * 1024
MONEY_CATEGORIES = {'contract', 'receipt'}


def visible_documents(user, queryset):
    if role(user) not in MONEY_READERS:
        queryset = queryset.exclude(category__in=MONEY_CATEGORIES)
    return queryset


def upload(actor, key, project_id, category, file):
    if category not in Document.Category.values:
        raise ValidationError({'category': '请选择有效的附件分类。'})
    roles = MANAGERS if category == 'contract' else FINANCE if category == 'receipt' else ALL_ROLES
    require_role(actor, roles)
    if file is None or not hasattr(file, 'read'):
        raise ValidationError({'file': '请选择文件。'})
    name = Path(file.name.replace('\\', '/')).name
    if not name or len(name) > 250 or any(ord(char) < 32 for char in name):
        raise ValidationError({'file': '文件名无效或超过 250 字符。'})
    content = file.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise ValidationError({'file': '附件不能为空且不能超过 20 MB。'})
    digest = hashlib.sha256(content).hexdigest()
    written = []

    def execute(user, project):
        if project.status == 'closed' or (project.status == 'cancelled' and category != 'receipt'):
            raise Conflict('当前项目只能补充取消后的结算凭证，其他附件需重新打开项目。')
        document = Document(project=project, category=category, original_name=name, size=len(content), sha256=digest)
        document.file.save(uuid.uuid4().hex, ContentFile(content), save=False)
        written.append((document.file.storage, document.file.name))
        save(document, user)
        return audit(user, 'document.upload', document, filename=name, sha256=digest, category=category)

    try:
        return project_action(
            actor,
            key,
            'document.upload',
            identity(project_id, 'project'),
            {'category': category, 'name': name, 'size': len(content), 'sha256': digest},
            roles,
            execute,
        )
    except Exception:
        for storage, path in written:
            storage.delete(path)
        raise
