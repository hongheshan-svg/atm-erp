"""钉钉(DingTalk)扫码登录适配器(新版 OAuth2)。

复用 settings.DINGTALK_APP_KEY/APP_SECRET(新版扫码登录的 clientId/clientSecret;
若企业用独立"扫码登录应用"凭据,联调时确认与 APP_KEY/SECRET 是否同源)。
端点参考(按当下官方文档核对):
- 授权:https://login.dingtalk.com/oauth2/auth
- code→用户token:POST https://api.dingtalk.com/v1.0/oauth2/userAccessToken
- 用户信息:GET https://api.dingtalk.com/v1.0/contact/users/me

external_id 取 unionId(跨应用稳定唯一)。注意:现有 dingtalk_id 字段亦用于通知发消息(那里通常需企业 userid),
本登录流程把 unionId 写入 dingtalk_id 仅用于身份绑定;通知模块如依赖 userid 需另行确认(见计划 Open items)。
"""
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import HTTP_TIMEOUT, BaseOAuthProvider, OAuthError, OAuthIdentity, register

logger = logging.getLogger(__name__)
DINGTALK = 'https://api.dingtalk.com'


@register
class DingTalkProvider(BaseOAuthProvider):
    platform = 'dingtalk'
    display_name = '钉钉'
    id_field = 'dingtalk_id'

    def is_configured(self) -> bool:
        return bool(settings.DINGTALK_APP_KEY and settings.DINGTALK_APP_SECRET)

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'client_id': settings.DINGTALK_APP_KEY,
            'scope': 'openid',
            'state': state,
            'prompt': 'consent',
        }
        return 'https://login.dingtalk.com/oauth2/auth?' + urlencode(params)

    def resolve_identity(self, code: str) -> OAuthIdentity:
        tr = requests.post(
            f'{DINGTALK}/v1.0/oauth2/userAccessToken',
            json={
                'clientId': settings.DINGTALK_APP_KEY,
                'clientSecret': settings.DINGTALK_APP_SECRET,
                'code': code,
                'grantType': 'authorization_code',
            },
            timeout=HTTP_TIMEOUT,
        ).json()
        user_token = tr.get('accessToken')
        if not user_token:
            logger.error('钉钉 userAccessToken 失败')
            raise OAuthError('钉钉用户令牌获取失败')

        me = requests.get(
            f'{DINGTALK}/v1.0/contact/users/me',
            headers={'x-acs-dingtalk-access-token': user_token},
            timeout=HTTP_TIMEOUT,
        ).json()
        unionid = me.get('unionId')
        if not unionid:
            logger.error('钉钉 users/me 缺少 unionId')
            raise OAuthError('钉钉用户信息获取失败')
        return OAuthIdentity(
            external_id=str(unionid),
            unionid=str(unionid),
            name=me.get('nick', ''),
            mobile=me.get('mobile', ''),
            email=me.get('email', ''),
            avatar=me.get('avatarUrl', ''),
        )
