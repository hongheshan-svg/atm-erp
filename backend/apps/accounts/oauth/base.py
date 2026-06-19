"""企业 IM(企业微信/钉钉/飞书)扫码登录的 OAuth 抽象层。

- 平台无关接口 BaseOAuthProvider + 标准身份字典 OAuthIdentity。
- access_token 缓存复刻 apps.oa.wechat_work 的 redis 模式(提前 5min 过期)。
- 所有出站请求固定官方域名 + 超时;secret/token/code/原始返回**绝不进日志**。
"""
import abc
import logging
from dataclasses import dataclass, field

from django.core.cache import cache

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 10  # 秒,所有出站三方请求统一超时,防 SSRF/挂死


@dataclass
class OAuthIdentity:
    """从三方解析出的标准身份(平台无关)。raw 仅供调试,严禁进日志。"""

    external_id: str  # 平台内稳定唯一标识(企微 userid / 钉钉 unionId / 飞书 union_id)
    unionid: str = ''
    name: str = ''
    mobile: str = ''
    email: str = ''
    avatar: str = ''
    dept_name: str = ''
    raw: dict = field(default_factory=dict)


class OAuthError(Exception):
    """OAuth 流程错误(配置缺失 / 网络 / 平台返回错误码 / 非企业成员)。"""


class BaseOAuthProvider(abc.ABC):
    platform = ''  # 'wecom' | 'dingtalk' | 'feishu'
    display_name = ''
    id_field = ''  # User 上的绑定字段:wechat_work_id / dingtalk_id / feishu_id

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """该平台 secret 是否齐全(供可发现性端点决定是否显示按钮)。"""

    @abc.abstractmethod
    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """构造扫码授权 URL。"""

    @abc.abstractmethod
    def resolve_identity(self, code: str) -> OAuthIdentity:
        """code → 平台 token → 用户信息 → 标准身份。失败抛 OAuthError。"""


def cached_app_token(cache_key: str, fetcher, min_ttl: int = 60):
    """redis 缓存平台级 access_token,提前 300s 过期。fetcher() -> (token, expires_in)。"""
    token = cache.get(cache_key)
    if token:
        return token
    token, expires_in = fetcher()
    if token:
        cache.set(cache_key, token, max(int(expires_in) - 300, min_ttl))
    return token


# 适配器注册表(由各适配器模块导入时通过 @register 填充)。
_PROVIDERS: dict[str, type] = {}


def register(cls):
    _PROVIDERS[cls.platform] = cls
    return cls


def get_provider(platform: str) -> BaseOAuthProvider:
    cls = _PROVIDERS.get(platform)
    if cls is None:
        raise OAuthError(f'unknown platform: {platform}')
    return cls()


def all_providers() -> list:
    return [cls() for cls in _PROVIDERS.values()]
