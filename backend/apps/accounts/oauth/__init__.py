"""企业 IM 扫码登录(企业微信/钉钉/飞书)。

导入三个适配器以触发 @register 注册;对外暴露 provider 查询与建号服务。
"""
from . import dingtalk, feishu, wecom  # noqa: F401  (导入即注册到 _PROVIDERS)
from .base import BaseOAuthProvider, OAuthError, OAuthIdentity, all_providers, get_provider
from .services import find_or_create_user

__all__ = [
    'BaseOAuthProvider',
    'OAuthError',
    'OAuthIdentity',
    'all_providers',
    'get_provider',
    'find_or_create_user',
]
