"""
Multi-channel notification service supporting:
- In-app notifications
- Email
- DingTalk (钉钉)
- WeChat Work (企业微信)
- SMS (optional)
"""
import json
import logging
import requests
import hashlib
import base64
import hmac
import time
from urllib.parse import quote_plus
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class NotificationChannel:
    """Base class for notification channels."""
    
    def send(self, recipient, title, content, **kwargs):
        raise NotImplementedError


class EmailChannel(NotificationChannel):
    """Email notification channel."""
    
    def send(self, recipient, title, content, **kwargs):
        """
        Send email notification.
        recipient: email address
        """
        try:
            send_mail(
                subject=title,
                message=content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            logger.info(f"Email sent to {recipient}: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False


class DingTalkChannel(NotificationChannel):
    """
    DingTalk (钉钉) notification channel.
    
    Supports:
    - Robot webhook (群机器人)
    - Work notification (工作通知)
    """
    
    def __init__(self):
        self.webhook_url = getattr(settings, 'DINGTALK_WEBHOOK_URL', '')
        self.webhook_secret = getattr(settings, 'DINGTALK_WEBHOOK_SECRET', '')
        self.app_key = getattr(settings, 'DINGTALK_APP_KEY', '')
        self.app_secret = getattr(settings, 'DINGTALK_APP_SECRET', '')
        self.agent_id = getattr(settings, 'DINGTALK_AGENT_ID', '')
    
    def _get_sign(self):
        """Generate signature for webhook with secret."""
        if not self.webhook_secret:
            return '', ''
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.webhook_secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.webhook_secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign
    
    def _get_access_token(self):
        """Get access token for work notification API."""
        if not self.app_key or not self.app_secret:
            return None
        
        url = f'https://oapi.dingtalk.com/gettoken?appkey={self.app_key}&appsecret={self.app_secret}'
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get('errcode') == 0:
                return data.get('access_token')
            logger.error(f"DingTalk get token error: {data}")
        except Exception as e:
            logger.error(f"DingTalk get token failed: {e}")
        return None
    
    def send_webhook(self, title, content, msg_type='text', at_mobiles=None, at_all=False):
        """
        Send message via robot webhook.
        
        Args:
            title: Message title (for markdown type)
            content: Message content
            msg_type: 'text', 'markdown', 'actionCard'
            at_mobiles: List of mobile numbers to @
            at_all: Whether to @ all members
        """
        if not self.webhook_url:
            logger.warning("DingTalk webhook URL not configured")
            return False
        
        url = self.webhook_url
        if self.webhook_secret:
            timestamp, sign = self._get_sign()
            url = f"{url}&timestamp={timestamp}&sign={sign}"
        
        if msg_type == 'text':
            data = {
                "msgtype": "text",
                "text": {"content": content},
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": at_all
                }
            }
        elif msg_type == 'markdown':
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": content
                },
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": at_all
                }
            }
        else:
            data = {
                "msgtype": "text",
                "text": {"content": f"{title}\n{content}"}
            }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"DingTalk webhook sent: {title}")
                return True
            else:
                logger.error(f"DingTalk webhook error: {result}")
                return False
        except Exception as e:
            logger.error(f"DingTalk webhook failed: {e}")
            return False
    
    def send_work_notification(self, user_ids, title, content):
        """
        Send work notification to specific users.
        
        Args:
            user_ids: List of DingTalk user IDs
            title: Message title
            content: Message content
        """
        access_token = self._get_access_token()
        if not access_token:
            return False
        
        url = f'https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token={access_token}'
        
        data = {
            "agent_id": self.agent_id,
            "userid_list": ",".join(user_ids) if isinstance(user_ids, list) else user_ids,
            "msg": {
                "msgtype": "oa",
                "oa": {
                    "head": {
                        "bgcolor": "FFBBBBBB",
                        "text": "ERP系统通知"
                    },
                    "body": {
                        "title": title,
                        "content": content
                    }
                }
            }
        }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"DingTalk work notification sent: {title}")
                return True
            else:
                logger.error(f"DingTalk work notification error: {result}")
                return False
        except Exception as e:
            logger.error(f"DingTalk work notification failed: {e}")
            return False
    
    def send(self, recipient, title, content, **kwargs):
        """Send notification via DingTalk."""
        msg_type = kwargs.get('msg_type', 'text')
        use_work_notification = kwargs.get('use_work_notification', False)
        
        if use_work_notification and recipient:
            return self.send_work_notification([recipient], title, content)
        else:
            return self.send_webhook(title, content, msg_type)


class WeChatWorkChannel(NotificationChannel):
    """
    WeChat Work (企业微信) notification channel.
    
    Supports:
    - Robot webhook (群机器人)
    - Application message (应用消息)
    """
    
    def __init__(self):
        self.webhook_url = getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', '')
        self.corp_id = getattr(settings, 'WECHAT_WORK_CORP_ID', '')
        self.corp_secret = getattr(settings, 'WECHAT_WORK_CORP_SECRET', '')
        self.agent_id = getattr(settings, 'WECHAT_WORK_AGENT_ID', '')
        self._access_token = None
        self._token_expires_at = 0
    
    def _get_access_token(self):
        """Get access token for application message API."""
        if not self.corp_id or not self.corp_secret:
            return None
        
        # Check if token is still valid
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.corp_secret}'
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get('errcode') == 0:
                self._access_token = data.get('access_token')
                self._token_expires_at = time.time() + data.get('expires_in', 7200) - 300
                return self._access_token
            logger.error(f"WeChat Work get token error: {data}")
        except Exception as e:
            logger.error(f"WeChat Work get token failed: {e}")
        return None
    
    def send_webhook(self, title, content, msg_type='text', mentioned_list=None):
        """
        Send message via robot webhook.
        
        Args:
            title: Message title (for markdown type)
            content: Message content
            msg_type: 'text', 'markdown'
            mentioned_list: List of user IDs to mention
        """
        if not self.webhook_url:
            logger.warning("WeChat Work webhook URL not configured")
            return False
        
        if msg_type == 'text':
            data = {
                "msgtype": "text",
                "text": {
                    "content": f"{title}\n{content}",
                    "mentioned_list": mentioned_list or []
                }
            }
        elif msg_type == 'markdown':
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {title}\n{content}"
                }
            }
        else:
            data = {
                "msgtype": "text",
                "text": {"content": f"{title}\n{content}"}
            }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"WeChat Work webhook sent: {title}")
                return True
            else:
                logger.error(f"WeChat Work webhook error: {result}")
                return False
        except Exception as e:
            logger.error(f"WeChat Work webhook failed: {e}")
            return False
    
    def send_app_message(self, user_ids, title, content):
        """
        Send application message to specific users.
        
        Args:
            user_ids: List of WeChat Work user IDs or '@all'
            title: Message title
            content: Message content
        """
        access_token = self._get_access_token()
        if not access_token:
            return False
        
        url = f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}'
        
        touser = "|".join(user_ids) if isinstance(user_ids, list) else user_ids
        
        data = {
            "touser": touser,
            "msgtype": "textcard",
            "agentid": self.agent_id,
            "textcard": {
                "title": title,
                "description": content[:512],  # Max 512 chars
                "url": getattr(settings, 'FRONTEND_URL', 'http://localhost'),
                "btntxt": "查看详情"
            }
        }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"WeChat Work app message sent: {title}")
                return True
            else:
                logger.error(f"WeChat Work app message error: {result}")
                return False
        except Exception as e:
            logger.error(f"WeChat Work app message failed: {e}")
            return False
    
    def send(self, recipient, title, content, **kwargs):
        """Send notification via WeChat Work."""
        msg_type = kwargs.get('msg_type', 'text')
        use_app_message = kwargs.get('use_app_message', False)
        
        if use_app_message and recipient:
            return self.send_app_message([recipient], title, content)
        else:
            return self.send_webhook(title, content, msg_type)


class NotificationService:
    """
    Unified notification service supporting multiple channels.
    """
    
    CHANNELS = {
        'email': EmailChannel,
        'dingtalk': DingTalkChannel,
        'wechat_work': WeChatWorkChannel,
    }
    
    def __init__(self):
        self._channel_instances = {}
    
    def _get_channel(self, channel_name):
        """Get or create channel instance."""
        if channel_name not in self._channel_instances:
            channel_class = self.CHANNELS.get(channel_name)
            if channel_class:
                self._channel_instances[channel_name] = channel_class()
            else:
                raise ValueError(f"Unknown notification channel: {channel_name}")
        return self._channel_instances[channel_name]
    
    def send(self, channel, recipient, title, content, **kwargs):
        """
        Send notification via specified channel.
        
        Args:
            channel: 'email', 'dingtalk', 'wechat_work'
            recipient: Channel-specific recipient identifier
            title: Notification title
            content: Notification content
            **kwargs: Channel-specific options
        """
        try:
            channel_instance = self._get_channel(channel)
            return channel_instance.send(recipient, title, content, **kwargs)
        except Exception as e:
            logger.error(f"Notification send failed ({channel}): {e}")
            return False
    
    def send_multi(self, channels, recipient_map, title, content, **kwargs):
        """
        Send notification via multiple channels.
        
        Args:
            channels: List of channel names
            recipient_map: Dict mapping channel name to recipient
            title: Notification title
            content: Notification content
            **kwargs: Channel-specific options
        
        Returns:
            Dict with results for each channel
        """
        results = {}
        for channel in channels:
            recipient = recipient_map.get(channel)
            if recipient:
                results[channel] = self.send(channel, recipient, title, content, **kwargs)
            else:
                results[channel] = False
        return results
    
    def broadcast(self, title, content, channels=None, **kwargs):
        """
        Broadcast notification to all configured channels.
        Uses webhook/robot mode (no specific recipient).
        
        Args:
            title: Notification title
            content: Notification content
            channels: List of channels to use, or None for all
            **kwargs: Channel-specific options
        """
        if channels is None:
            channels = ['dingtalk', 'wechat_work']
        
        results = {}
        for channel in channels:
            if channel in ['dingtalk', 'wechat_work']:
                results[channel] = self.send(channel, None, title, content, **kwargs)
        return results


# Global service instance
notification_service = NotificationService()


# Convenience functions
def send_notification(channel, recipient, title, content, **kwargs):
    """Send notification via specified channel."""
    return notification_service.send(channel, recipient, title, content, **kwargs)


def broadcast_notification(title, content, channels=None, **kwargs):
    """Broadcast notification to all configured channels."""
    return notification_service.broadcast(title, content, channels, **kwargs)


def send_dingtalk(title, content, msg_type='markdown', **kwargs):
    """Send DingTalk notification."""
    dingtalk = notification_service._get_channel('dingtalk')
    return dingtalk.send_webhook(title, content, msg_type, **kwargs)


def send_wechat_work(title, content, msg_type='markdown', **kwargs):
    """Send WeChat Work notification."""
    wechat = notification_service._get_channel('wechat_work')
    return wechat.send_webhook(title, content, msg_type, **kwargs)

