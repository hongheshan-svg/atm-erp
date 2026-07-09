"""多组织 / 多法人主数据 + 公司范围管理器(平台基础脚手架)。

本模块是“多组织”能力的**基础脚手架**,提供:
- Organization: 组织树(集团/事业部/子公司的层级结构)。
- Company: 法人实体(税号等),挂到某个 Organization 节点。
- CompanyScopedManager: 镜像 SoftDeleteManager 的软删除过滤,并**可选**按“当前上下文
  公司集合”过滤;默认**不做任何公司过滤**,因此不影响任何既有查询/行为。

**明确的 foundation vs 完成边界(多周后续,非本次):**
本次只落地“组织/公司主数据 + 一个可复用的范围管理器与上下文开关”。真正的多租户隔离
需要:在 apps.core.models.BaseModel 上新增 `company` 外键(null=True 向后兼容)、为每个
业务模型接入 CompanyScopedManager、编写把存量数据回填到默认公司的数据迁移、在请求中间件
里根据登录用户设置活动公司上下文、并对写入路径强制赋值 company——这些均为后续里程碑。
当前 CompanyScopedManager 默认不过滤,保证接入前后行为一致。
"""

from __future__ import annotations

import contextlib
import contextvars

from django.db import models

from apps.core.models import BaseModel, SoftDeleteManager

# 当前请求/线程的“活动公司集合”。默认 None 表示不做公司范围过滤(不影响既有行为)。
# 后续里程碑:由请求中间件依据登录用户在此设置可见公司集合。
_active_company_ids: contextvars.ContextVar[frozenset[int] | None] = contextvars.ContextVar(
    'ai_active_company_ids', default=None
)


def set_active_companies(company_ids) -> contextvars.Token:
    """设置当前上下文的活动公司集合。返回 token,可用于 reset。"""
    value = None if company_ids is None else frozenset(int(c) for c in company_ids)
    return _active_company_ids.set(value)


def get_active_companies() -> frozenset[int] | None:
    """读取当前上下文的活动公司集合(None 表示不过滤)。"""
    return _active_company_ids.get()


def reset_active_companies(token: contextvars.Token) -> None:
    _active_company_ids.reset(token)


@contextlib.contextmanager
def company_scope(company_ids):
    """临时限定活动公司集合的上下文管理器(with company_scope([1,2]): ...)。"""
    token = set_active_companies(company_ids)
    try:
        yield
    finally:
        reset_active_companies(token)


class CompanyScopedManager(SoftDeleteManager):
    """在软删除过滤之外,叠加可选的“公司范围”过滤的管理器。

    - 继承 SoftDeleteManager:默认过滤 is_deleted=False(与现有约定一致)。
    - 若当前上下文设置了活动公司集合,且模型存在 `company` 字段,则追加
      `company_id__in=<集合>` 过滤;否则**不做任何公司过滤**。

    这样接入前(模型无 company 字段或未设置上下文)行为与 SoftDeleteManager 完全一致,
    是安全的、向后兼容的多组织范围基础。
    """

    def get_queryset(self):
        qs = super().get_queryset()
        company_ids = get_active_companies()
        if company_ids is None:
            return qs
        field_names = {f.name for f in self.model._meta.get_fields()}
        if 'company' not in field_names:
            return qs
        return qs.filter(company_id__in=company_ids)


class Organization(BaseModel):
    """组织节点(集团/事业部/子公司的树形结构)。"""

    name = models.CharField(max_length=200, verbose_name='组织名称')
    code = models.CharField(max_length=50, unique=True, blank=True, verbose_name='组织编码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级组织',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'core_organization'
        verbose_name = '组织'
        verbose_name_plural = verbose_name
        ordering = ['code', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            from apps.core.utils import generate_code

            self.code = generate_code('ORG')
        super().save(*args, **kwargs)


class Company(BaseModel):
    """法人实体(挂到某个组织节点,承载税号等法务信息)。"""

    name = models.CharField(max_length=200, verbose_name='公司名称')
    code = models.CharField(max_length=50, unique=True, blank=True, verbose_name='公司编码')
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='companies',
        null=True,
        blank=True,
        verbose_name='所属组织',
    )
    tax_no = models.CharField(max_length=50, blank=True, verbose_name='税号')
    legal_representative = models.CharField(max_length=50, blank=True, verbose_name='法人代表')
    address = models.CharField(max_length=300, blank=True, verbose_name='注册地址')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'core_company'
        verbose_name = '公司(法人)'
        verbose_name_plural = verbose_name
        ordering = ['code', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            from apps.core.utils import generate_code

            self.code = generate_code('COM')
        super().save(*args, **kwargs)
