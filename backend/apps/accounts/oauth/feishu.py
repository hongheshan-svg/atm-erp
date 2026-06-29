"""飞书(Feishu/Lark)扫码登录适配器。

需 settings.FEISHU_APP_ID/APP_SECRET。端点参考(按当下官方文档核对):
- 授权:https://open.feishu.cn/open-apis/authen/v1/authorize
- app_access_token:POST /open-apis/auth/v3/app_access_token/internal
- code→user token:POST /open-apis/authen/v1/oidc/access_token
- 用户信息:GET /open-apis/authen/v1/user_info

external_id 取 union_id(跨应用稳定),回退 open_id。
"""
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import HTTP_TIMEOUT, BaseOAuthProvider, OAuthError, OAuthIdentity, cached_app_token, register

logger = logging.getLogger(__name__)
FEISHU = 'https://open.feishu.cn'


@register
class FeishuProvider(BaseOAuthProvider):
    platform = 'feishu'
    display_name = '飞书'
    id_field = 'feishu_id'

    def is_configured(self) -> bool:
        return bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET)

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {'app_id': settings.FEISHU_APP_ID, 'redirect_uri': redirect_uri, 'state': state}
        return f'{FEISHU}/open-apis/authen/v1/authorize?' + urlencode(params)

    def _app_token(self) -> str:
        def fetch():
            r = requests.post(
                f'{FEISHU}/open-apis/auth/v3/app_access_token/internal',
                json={'app_id': settings.FEISHU_APP_ID, 'app_secret': settings.FEISHU_APP_SECRET},
                timeout=HTTP_TIMEOUT,
            ).json()
            if r.get('code') == 0:
                return r.get('app_access_token'), r.get('expire', 7200)
            logger.error('飞书 app_access_token 失败 code=%s', r.get('code'))
            return None, 0

        token = cached_app_token('oauth_feishu_app_token', fetch)
        if not token:
            raise OAuthError('飞书应用令牌获取失败')
        return token

    def resolve_identity(self, code: str) -> OAuthIdentity:
        app_token = self._app_token()
        tr = requests.post(
            f'{FEISHU}/open-apis/authen/v1/oidc/access_token',
            json={'grant_type': 'authorization_code', 'code': code},
            headers={'Authorization': f'Bearer {app_token}'},
            timeout=HTTP_TIMEOUT,
        ).json()
        if tr.get('code') != 0 or 'data' not in tr:
            logger.error('飞书 access_token 失败 code=%s', tr.get('code'))
            raise OAuthError('飞书用户令牌获取失败')
        user_token = tr['data'].get('access_token')
        if not user_token:
            raise OAuthError('飞书用户令牌缺失')

        ui = requests.get(
            f'{FEISHU}/open-apis/authen/v1/user_info',
            headers={'Authorization': f'Bearer {user_token}'},
            timeout=HTTP_TIMEOUT,
        ).json()
        if ui.get('code') != 0 or 'data' not in ui:
            logger.error('飞书 user_info 失败 code=%s', ui.get('code'))
            raise OAuthError('飞书用户信息获取失败')
        d = ui['data']
        external = d.get('union_id') or d.get('open_id')
        if not external:
            raise OAuthError('飞书用户标识缺失')
        return OAuthIdentity(
            external_id=str(external),
            unionid=str(d.get('union_id', '')),
            name=d.get('name', ''),
            mobile=d.get('mobile', ''),
            email=d.get('email') or d.get('enterprise_email', ''),
            avatar=d.get('avatar_url', ''),
        )
