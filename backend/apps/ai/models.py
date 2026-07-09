"""AI 网关最小持久化模型:会话与消息(历史/审计)。

这是 AI 平台能力的基础脚手架:记录每次对话的 provider/model 与逐条消息,
便于审计、成本追踪与后续 RAG 上下文回放。完整的 token 计量、向量索引、
反馈标注等为后续里程碑。
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class AIConversation(BaseModel):
    """AI 对话会话(一次多轮对话的容器)。"""

    title = models.CharField(max_length=200, blank=True, default='', verbose_name='会话标题')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_conversations',
        verbose_name='所属用户',
    )
    provider = models.CharField(max_length=50, blank=True, default='', verbose_name='LLM Provider')
    model = models.CharField(max_length=100, blank=True, default='', verbose_name='模型')
    # 业务场景标记(如 'qa' / 'rag' / 'summary'),用于后续分场景计量与治理。
    scene = models.CharField(max_length=50, blank=True, default='', verbose_name='业务场景')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='扩展元数据')

    class Meta:
        db_table = 'ai_conversation'
        verbose_name = 'AI 会话'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'AIConversation#{self.pk}'


class AIMessage(BaseModel):
    """AI 对话中的单条消息(system/user/assistant)。"""

    ROLE_CHOICES = [
        ('system', '系统'),
        ('user', '用户'),
        ('assistant', '助手'),
    ]

    conversation = models.ForeignKey(
        AIConversation, on_delete=models.CASCADE, related_name='messages', verbose_name='所属会话'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user', verbose_name='角色')
    content = models.TextField(blank=True, default='', verbose_name='内容')
    # provider 返回的 token 计量(NullProvider 下为 0);完整计量为后续里程碑。
    tokens = models.IntegerField(default=0, verbose_name='Token 数')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='扩展元数据')

    class Meta:
        db_table = 'ai_message'
        verbose_name = 'AI 消息'
        verbose_name_plural = verbose_name
        ordering = ['conversation', 'created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_role_display()}: {self.content[:30]}'
