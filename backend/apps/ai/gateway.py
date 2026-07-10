"""LLM 网关:provider 抽象 + 路由 + 日志。

设计目标(平台基础脚手架,非完成):
- 默认关闭:未配置 settings.AI_PROVIDER 时使用 NullProvider,返回明确的“未配置”
  响应,不发起任何网络调用——测试与无 AI 依赖/密钥的环境均可正常 import 与运行。
- provider 抽象:BaseProvider 定义统一 chat() 契约;NullProvider 为始终可用的
  默认实现;真实 provider(如 AnthropicProvider)惰性导入其 SDK,未安装也不影响本
  模块 import。
- 可观测:LLMGateway.chat() 统一记录日志并路由到具体 provider。

后续里程碑(完成项):真实流式响应、token 计量与成本入账、重试/限流、多 provider
负载与回退、与 AIConversation/AIMessage 的持久化打通(当前由 views 层负责落库)。
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseProvider:
    """LLM provider 抽象基类。子类实现 chat()。"""

    name = 'base'

    def __init__(self, api_key: str = '', model: str = ''):
        self.api_key = api_key
        self.model = model

    @property
    def configured(self) -> bool:
        """是否已具备发起真实调用的条件(密钥齐全)。"""
        return bool(self.api_key)

    def chat(self, messages: list[dict], **kwargs) -> dict:  # pragma: no cover - 抽象方法
        raise NotImplementedError


class NullProvider(BaseProvider):
    """默认 provider:不发起任何网络调用,返回明确的“未配置”响应。

    这是网关在未配置真实 provider 时的安全兜底,保证 AI 接口始终可用且可预测。
    """

    name = 'null'

    @property
    def configured(self) -> bool:
        return False

    def chat(self, messages: list[dict], **kwargs) -> dict:
        return {
            'provider': self.name,
            'model': self.model or '',
            'configured': False,
            'content': (
                'AI 网关尚未配置 LLM Provider。请设置 settings.AI_PROVIDER 与 AI_API_KEY '
                '后重试(默认关闭,不产生任何外部调用)。'
            ),
            'usage': {'total_tokens': 0},
        }


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider(惰性导入 SDK,真实调用为后续里程碑)。

    仅当 settings.AI_PROVIDER='anthropic' 且配置了 AI_API_KEY 时才会被实例化并调用。
    SDK(`anthropic`)在 chat() 内部惰性导入——未安装时抛出清晰错误而非在模块 import
    阶段失败,从而保证无 AI 依赖时本模块仍可 import/运行。默认模型见 settings.AI_MODEL
    (claude-opus-4-8)。真实网络调用不在测试路径中执行。
    """

    name = 'anthropic'

    def chat(self, messages: list[dict], **kwargs) -> dict:
        if not self.configured:
            # 无密钥时不尝试导入或调用,直接回落到“未配置”语义。
            return NullProvider(model=self.model).chat(messages, **kwargs)
        try:
            import anthropic  # noqa: F401  (惰性导入,避免无依赖时 import 失败)
        except ImportError as exc:  # pragma: no cover - 依赖缺失路径
            raise RuntimeError(
                "AI_PROVIDER='anthropic' 但未安装 anthropic SDK,请先 `pip install anthropic`。"
            ) from exc

        # 真实调用实现(流式/计量/重试)为后续里程碑。此处保留清晰的占位实现,
        # 拆分出 system 与对话消息以对齐 Anthropic Messages API 的入参形态。
        client = anthropic.Anthropic(api_key=self.api_key)  # pragma: no cover
        system_prompt = '\n'.join(m.get('content', '') for m in messages if m.get('role') == 'system')
        chat_messages = [m for m in messages if m.get('role') in ('user', 'assistant')]
        response = client.messages.create(  # pragma: no cover
            model=self.model or 'claude-opus-4-8',
            max_tokens=kwargs.get('max_tokens', 1024),
            system=system_prompt or None,
            messages=chat_messages,
        )
        text = ''.join(block.text for block in response.content if getattr(block, 'type', None) == 'text')
        return {  # pragma: no cover
            'provider': self.name,
            'model': self.model or 'claude-opus-4-8',
            'configured': True,
            'content': text,
            'usage': {'total_tokens': getattr(response.usage, 'output_tokens', 0)},
        }


# provider 名称 -> 类 的注册表。新增真实 provider 时在此登记即可。
PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    'null': NullProvider,
    'anthropic': AnthropicProvider,
}


class LLMGateway:
    """LLM 网关入口:根据配置解析 provider 并路由 chat 请求。"""

    def __init__(self, provider: str | None = None, api_key: str | None = None, model: str | None = None):
        self.provider_name = (provider if provider is not None else getattr(settings, 'AI_PROVIDER', '')) or ''
        self.api_key = api_key if api_key is not None else getattr(settings, 'AI_API_KEY', '')
        self.model = model if model is not None else getattr(settings, 'AI_MODEL', '')
        self.provider = self._resolve_provider()

    def _resolve_provider(self) -> BaseProvider:
        """解析 provider。未配置或未注册或缺密钥时一律回落到 NullProvider。"""
        name = (self.provider_name or '').strip().lower()
        if not name or not self.api_key:
            return NullProvider(model=self.model)
        provider_cls = PROVIDER_REGISTRY.get(name)
        if provider_cls is None:
            logger.warning("未知的 AI_PROVIDER=%r,回落到 NullProvider", self.provider_name)
            return NullProvider(model=self.model)
        return provider_cls(api_key=self.api_key, model=self.model)

    @property
    def configured(self) -> bool:
        return self.provider.configured

    def chat(self, messages: list[dict], **kwargs) -> dict:
        """路由一次对话请求。记录日志(不含消息正文,避免敏感信息泄漏)。"""
        logger.info(
            'LLMGateway.chat provider=%s configured=%s messages=%d',
            self.provider.name,
            self.provider.configured,
            len(messages or []),
        )
        return self.provider.chat(messages or [], **kwargs)
