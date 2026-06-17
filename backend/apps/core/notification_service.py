"""
Notification service for external integrations (DingTalk, WeChat Work).
"""

import base64
import hashlib
import hmac
import logging
import time
from urllib.parse import quote_plus

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class DingTalkNotification:
    """
    DingTalk (钉钉) webhook notification service.

    Configuration in settings.py:
        DINGTALK_WEBHOOK_URL = 'https://oapi.dingtalk.com/robot/send?access_token=xxx'
        DINGTALK_SECRET = 'your_secret'  # Optional, for signed messages
    """

    @classmethod
    def _get_sign(cls, timestamp, secret):
        """Generate signature for DingTalk webhook."""
        string_to_sign = f'{timestamp}\n{secret}'
        hmac_code = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
        sign = quote_plus(base64.b64encode(hmac_code))
        return sign

    @classmethod
    def _get_webhook_url(cls):
        """Get webhook URL with signature if secret is configured."""
        base_url = getattr(settings, 'DINGTALK_WEBHOOK_URL', None)
        secret = getattr(settings, 'DINGTALK_SECRET', None)

        if not base_url:
            return None

        if secret:
            timestamp = str(round(time.time() * 1000))
            sign = cls._get_sign(timestamp, secret)
            return f'{base_url}&timestamp={timestamp}&sign={sign}'

        return base_url

    @classmethod
    def send_text(cls, content, at_mobiles=None, at_all=False):
        """
        Send text message to DingTalk.

        Args:
            content: Message content
            at_mobiles: List of mobile numbers to @mention
            at_all: Whether to @all
        """
        webhook_url = cls._get_webhook_url()
        if not webhook_url:
            logger.warning('DingTalk webhook URL not configured')
            return False

        data = {
            'msgtype': 'text',
            'text': {'content': content},
            'at': {'atMobiles': at_mobiles or [], 'isAtAll': at_all},
        }

        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f'DingTalk send failed: {result}')
                return False
        except Exception as e:
            logger.error(f'DingTalk send error: {e}')
            return False

    @classmethod
    def send_markdown(cls, title, text, at_mobiles=None, at_all=False):
        """
        Send markdown message to DingTalk.

        Args:
            title: Message title
            text: Markdown content
            at_mobiles: List of mobile numbers to @mention
            at_all: Whether to @all
        """
        webhook_url = cls._get_webhook_url()
        if not webhook_url:
            logger.warning('DingTalk webhook URL not configured')
            return False

        data = {
            'msgtype': 'markdown',
            'markdown': {'title': title, 'text': text},
            'at': {'atMobiles': at_mobiles or [], 'isAtAll': at_all},
        }

        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f'DingTalk send failed: {result}')
                return False
        except Exception as e:
            logger.error(f'DingTalk send error: {e}')
            return False


class WeChatWorkNotification:
    """
    WeChat Work (企业微信) webhook notification service.

    Configuration in settings.py:
        WECHAT_WORK_WEBHOOK_URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
    """

    @classmethod
    def _get_webhook_url(cls):
        """Get webhook URL."""
        return getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', None)

    @classmethod
    def send_text(cls, content, mentioned_list=None, mentioned_mobile_list=None):
        """
        Send text message to WeChat Work.

        Args:
            content: Message content
            mentioned_list: List of user IDs to @mention
            mentioned_mobile_list: List of mobile numbers to @mention
        """
        webhook_url = cls._get_webhook_url()
        if not webhook_url:
            logger.warning('WeChat Work webhook URL not configured')
            return False

        data = {
            'msgtype': 'text',
            'text': {
                'content': content,
                'mentioned_list': mentioned_list or [],
                'mentioned_mobile_list': mentioned_mobile_list or [],
            },
        }

        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f'WeChat Work send failed: {result}')
                return False
        except Exception as e:
            logger.error(f'WeChat Work send error: {e}')
            return False

    @classmethod
    def send_markdown(cls, content):
        """
        Send markdown message to WeChat Work.

        Args:
            content: Markdown content
        """
        webhook_url = cls._get_webhook_url()
        if not webhook_url:
            logger.warning('WeChat Work webhook URL not configured')
            return False

        data = {'msgtype': 'markdown', 'markdown': {'content': content}}

        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f'WeChat Work send failed: {result}')
                return False
        except Exception as e:
            logger.error(f'WeChat Work send error: {e}')
            return False


class NotificationService:
    """
    Unified notification service that sends to all configured channels.
    """

    @classmethod
    def _is_dingtalk_enabled(cls):
        return bool(getattr(settings, 'DINGTALK_WEBHOOK_URL', None))

    @classmethod
    def _is_wechat_enabled(cls):
        return bool(getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', None))

    @classmethod
    def send_stock_alert(cls, low_stock_items):
        """
        Send low stock alert notification.

        Args:
            low_stock_items: List of dicts with item info
        """
        if not low_stock_items:
            return

        title = '📦 库存预警通知'

        # 群发安全内容（不含具体物料信息）
        safe_content = f'### {title}\n\n'
        safe_content += f'⚠️ **{len(low_stock_items)}** 种物料库存低于安全库存\n\n'
        safe_content += '请登录ERP系统查看详情并及时补货！'

        # Send to group channels (safe content)
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, safe_content)

        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(safe_content)

    @classmethod
    def send_approval_notification(cls, task):
        """
        Send approval task notification to the assignee (个人优先 + 群播兜底).

        Args:
            task: WorkflowTask instance
        """
        title = '📋 审批任务提醒'
        biz = task.instance.workflow.get_business_type_display()

        # 群播兜底脱敏内容（不含具体金额和人员）
        safe_content = f'### {title}\n\n'
        safe_content += f'您有一个新的 **{biz}** 审批任务待处理\n\n'
        safe_content += '请登录ERP系统查看详情并及时处理！'

        assignee = getattr(task, 'assignee', None)
        detail = f'您有一个新的 **{biz}** 审批任务待处理:单据 {task.instance.business_no}。请登录ERP及时处理。'
        cls.send_targeted_reminders(
            [(assignee, detail)] if assignee else [],
            title,
            safe_content,
            has_unassigned=(assignee is None),
        )

    @classmethod
    def send_workflow_result_notification(cls, instance, result):
        """
        Send workflow result notification to submitter.

        Args:
            instance: WorkflowInstance
            result: 'APPROVED', 'REJECTED', or 'WITHDRAWN'
        """
        result_emoji = {'APPROVED': '✅', 'REJECTED': '❌', 'WITHDRAWN': '↩️'}.get(result, '📋')

        result_text = {'APPROVED': '已通过', 'REJECTED': '已拒绝', 'WITHDRAWN': '已撤回'}.get(result, result)

        title = f'{result_emoji} 审批结果通知'
        biz = instance.workflow.get_business_type_display()

        # 群播兜底脱敏内容（不含具体金额）
        safe_content = f'### {title}\n\n'
        safe_content += f'您提交的 **{biz}** 审批{result_text}\n\n'
        safe_content += '请登录ERP系统查看详情。'

        submitter = getattr(instance, 'submitter', None)
        detail = f'您提交的 **{biz}** 审批{result_text}:单据 {instance.business_no}。'
        cls.send_targeted_reminders(
            [(submitter, detail)] if submitter else [],
            title,
            safe_content,
            has_unassigned=(submitter is None),
        )

    @classmethod
    def send_custom_notification(cls, title, content, at_mobiles=None, to_users=None, group_safe_content=None):
        """
        Send custom notification to all channels or specific users.

        Args:
            title: Notification title
            content: Notification content (markdown supported) - used for personal messages
            at_mobiles: List of mobile numbers to @mention (for group notifications)
            to_users: List of User objects or user IDs to send personal messages to
                     If provided, sends personal messages instead of group broadcast
            group_safe_content: Safe content for group broadcasts (no sensitive data)
                               If not provided, falls back to content
        """
        # If specific users are provided, send personal messages with detailed content
        if to_users:
            cls.send_personal_notification(to_users, title, content)
            return

        # For group channels, use safe content if provided
        broadcast_content = group_safe_content if group_safe_content else content

        # Send to group channels
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, broadcast_content, at_mobiles=at_mobiles)

        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(broadcast_content)

    @classmethod
    def send_personal_notification(cls, users, title, content):
        """
        Send personal notification to specific users via WeChat Work / DingTalk app message.

        Args:
            users: List of User objects, user IDs, or a queryset
            title: Notification title
            content: Notification content (will be truncated to 512 chars for WeChat)
        """
        from apps.accounts.models import User

        # Convert to user objects if needed
        if not users:
            return

        # If it's a queryset or list of IDs, fetch users
        if hasattr(users, 'values_list'):
            user_list = list(users)
        elif isinstance(users[0], int):
            user_list = list(User.objects.filter(id__in=users, is_active=True, is_deleted=False))
        else:
            user_list = users

        # Collect WeChat Work user IDs
        wechat_user_ids = []
        dingtalk_user_ids = []

        for user in user_list:
            if hasattr(user, 'wechat_work_id') and user.wechat_work_id:
                wechat_user_ids.append(user.wechat_work_id)
            if hasattr(user, 'dingtalk_id') and user.dingtalk_id:
                dingtalk_user_ids.append(user.dingtalk_id)

        # Send via WeChat Work app message
        if wechat_user_ids and cls._is_wechat_enabled():
            try:
                from apps.core.notification_channels import WeChatWorkChannel

                wechat = WeChatWorkChannel()
                # Truncate content for WeChat Work text card (max 512 chars)
                truncated_content = content[:500] + '...' if len(content) > 500 else content
                wechat.send_app_message(wechat_user_ids, title, truncated_content)
            except Exception as e:
                logger.error(f'Failed to send WeChat Work personal message: {e}')

        # Send via DingTalk work notification
        if dingtalk_user_ids and cls._is_dingtalk_enabled():
            try:
                from apps.core.notification_channels import DingTalkChannel

                dingtalk = DingTalkChannel()
                dingtalk.send_work_notification(dingtalk_user_ids, title, content)
            except Exception as e:
                logger.error(f'Failed to send DingTalk personal message: {e}')

    @classmethod
    def send_to_user(cls, user, title, content):
        """
        Send personal notification to a single user.

        Args:
            user: User object or user ID
            title: Notification title
            content: Notification content
        """
        from apps.accounts.models import User

        if isinstance(user, int):
            try:
                user = User.objects.get(id=user, is_active=True, is_deleted=False)
            except User.DoesNotExist:
                return False

        cls.send_personal_notification([user], title, content)
        return True

    @classmethod
    def send_payment_reminder(cls, payment_schedules):
        """
        Send payment collection reminder notification.

        Args:
            payment_schedules: List of PaymentSchedule instances that need reminders
        """
        if not payment_schedules:
            return

        # Group by urgency
        overdue = [p for p in payment_schedules if p.is_overdue]
        upcoming = [p for p in payment_schedules if not p.is_overdue]

        title = '💰 收款提醒通知'

        # 群发安全内容（不含具体财务数据）
        safe_content = f'### {title}\n\n'
        if overdue:
            safe_content += f'⚠️ **{len(overdue)}** 笔收款已逾期\n'
        if upcoming:
            safe_content += f'📅 **{len(upcoming)}** 笔收款即将到期\n'
        safe_content += '\n请登录ERP系统查看详情并及时跟进收款！'

        # Send to group channels (safe content only)
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, safe_content)

        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(safe_content)

    @classmethod
    def send_targeted_reminders(cls, personal_messages, title, group_safe_content, has_unassigned=False):
        """个人优先 + 群播兜底。

        personal_messages: list[(user, detail)] —— 对 is_active 且有 wechat_work_id 的责任人推个人；
        若有未分配项(has_unassigned)、有被跳过的责任人、或一个个人都没发出，则群播 group_safe_content 兜底。
        """
        sent = 0
        skipped = 0
        for user, content in personal_messages:
            if user and getattr(user, 'is_active', True) and getattr(user, 'wechat_work_id', ''):
                cls.send_to_user(user, title, content)
                sent += 1
            else:
                skipped += 1
        if has_unassigned or skipped > 0 or sent == 0:
            cls.send_custom_notification(title, group_safe_content, group_safe_content=group_safe_content)
        return {'personal_sent': sent, 'personal_skipped': skipped}
