"""企业微信(WeChat Work)扫码登录适配器。

复用 settings.WECHAT_WORK_CORP_ID/SECRET/AGENT_ID。
端点参考(实现/联调时按当下官方文档核对):
- PC 扫码授权:https://login.work.weixin.qq.com/wwlogin/sso/login
- code→userid:cgi-bin/auth/getuserinfo(旧路径 cgi-bin/user/getuserinfo)
- userid→详情:cgi-bin/user/get
"""
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import HTTP_TIMEOUT, BaseOAuthProvider, OAuthError, OAuthIdentity, cached_app_token, register

logger = logging.getLogger(__name__)
QYAPI = 'https://qyapi.weixin.qq.com'


@register
class WeComProvider(BaseOAuthProvider):
    platform = 'wecom'
    display_name = '企业微信'
    id_field = 'wechat_work_id'

    def is_configured(self) -> bool:
        return bool(settings.WECHAT_WORK_CORP_ID and settings.WECHAT_WORK_CORP_SECRET)

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            'login_type': 'CorpApp',
            'appid': settings.WECHAT_WORK_CORP_ID,
            'agentid': settings.WECHAT_WORK_AGENT_ID,
            'redirect_uri': redirect_uri,
            'state': state,
        }
        return 'https://login.work.weixin.qq.com/wwlogin/sso/login?' + urlencode(params)

    def _token(self) -> str:
        def fetch():
            r = requests.get(
                f'{QYAPI}/cgi-bin/gettoken',
                params={'corpid': settings.WECHAT_WORK_CORP_ID, 'corpsecret': settings.WECHAT_WORK_CORP_SECRET},
                timeout=HTTP_TIMEOUT,
            ).json()
            if r.get('errcode') == 0:
                return r.get('access_token'), r.get('expires_in', 7200)
            logger.error('企业微信 gettoken 失败 errcode=%s', r.get('errcode'))
            return None, 0

        token = cached_app_token('oauth_wecom_token', fetch)
        if not token:
            raise OAuthError('企业微信令牌获取失败')
        return token

    def resolve_identity(self, code: str) -> OAuthIdentity:
        token = self._token()
        info = requests.get(
            f'{QYAPI}/cgi-bin/auth/getuserinfo',
            params={'access_token': token, 'code': code},
            timeout=HTTP_TIMEOUT,
        ).json()
        if info.get('errcode') != 0:
            logger.error('企业微信 getuserinfo 失败 errcode=%s', info.get('errcode'))
            raise OAuthError('企业微信用户信息获取失败')
        userid = info.get('userid') or info.get('UserId')
        if not userid:
            # 仅返回 openid 说明是非企业成员(外部联系人),不支持登录
            raise OAuthError('非企业成员,无法登录')

        detail = requests.get(
            f'{QYAPI}/cgi-bin/user/get',
            params={'access_token': token, 'userid': userid},
            timeout=HTTP_TIMEOUT,
        ).json()
        if detail.get('errcode') != 0:
            detail = {}
        return OAuthIdentity(
            external_id=str(userid),
            name=detail.get('name', ''),
            mobile=detail.get('mobile', ''),
            email=detail.get('email') or detail.get('biz_mail', ''),
            avatar=detail.get('avatar', ''),
        )
