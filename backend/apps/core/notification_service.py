"""
Notification service for external integrations (DingTalk, WeChat Work).
"""
import logging
import requests
import hashlib
import hmac
import base64
import time
from urllib.parse import quote_plus
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
        hmac_code = hmac.new(
            secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
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
            return f"{base_url}&timestamp={timestamp}&sign={sign}"
        
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
            logger.warning("DingTalk webhook URL not configured")
            return False
        
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            },
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all
            }
        }
        
        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f"DingTalk send failed: {result}")
                return False
        except Exception as e:
            logger.error(f"DingTalk send error: {e}")
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
            logger.warning("DingTalk webhook URL not configured")
            return False
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text
            },
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all
            }
        }
        
        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f"DingTalk send failed: {result}")
                return False
        except Exception as e:
            logger.error(f"DingTalk send error: {e}")
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
            logger.warning("WeChat Work webhook URL not configured")
            return False
        
        data = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_list": mentioned_list or [],
                "mentioned_mobile_list": mentioned_mobile_list or []
            }
        }
        
        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f"WeChat Work send failed: {result}")
                return False
        except Exception as e:
            logger.error(f"WeChat Work send error: {e}")
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
            logger.warning("WeChat Work webhook URL not configured")
            return False
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        try:
            response = requests.post(webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                logger.error(f"WeChat Work send failed: {result}")
                return False
        except Exception as e:
            logger.error(f"WeChat Work send error: {e}")
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
        
        # Build message
        title = "📦 库存预警通知"
        lines = [f"### {title}\n", "以下物料库存不足，请及时补货：\n"]
        
        for item in low_stock_items[:10]:  # Limit to 10 items
            lines.append(
                f"- **{item['sku']}** {item['name']}\n"
                f"  - 仓库: {item['warehouse']}\n"
                f"  - 当前库存: {item['qty_on_hand']}\n"
                f"  - 安全库存: {item['min_stock']}\n"
            )
        
        if len(low_stock_items) > 10:
            lines.append(f"\n... 还有 {len(low_stock_items) - 10} 项\n")
        
        markdown_content = "".join(lines)
        text_content = f"{title}\n\n" + "\n".join([
            f"- {item['sku']} {item['name']}: 当前{item['qty_on_hand']}, 安全{item['min_stock']}"
            for item in low_stock_items[:10]
        ])
        
        # Send to all channels
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, markdown_content)
        
        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(markdown_content)
    
    @classmethod
    def send_approval_notification(cls, task):
        """
        Send approval task notification.
        
        Args:
            task: WorkflowTask instance
        """
        title = "📋 审批任务提醒"
        
        markdown_content = f"""### {title}

您有一个新的审批任务待处理：

- **单据类型**: {task.instance.workflow.get_business_type_display()}
- **单据编号**: {task.instance.business_no}
- **提交人**: {task.instance.submitter.get_full_name() or task.instance.submitter.username}
- **金额**: ¥{task.instance.amount or 0:,.2f}
- **审批步骤**: {task.step.name}
- **截止时间**: {task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else '无'}

请及时处理！
"""
        
        text_content = (
            f"{title}\n\n"
            f"单据: {task.instance.business_no}\n"
            f"类型: {task.instance.workflow.get_business_type_display()}\n"
            f"金额: ¥{task.instance.amount or 0:,.2f}\n"
            f"请及时处理！"
        )
        
        # Get assignee phone for @mention
        assignee_phone = task.assignee.phone if hasattr(task.assignee, 'phone') else None
        at_mobiles = [assignee_phone] if assignee_phone else []
        
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, markdown_content, at_mobiles=at_mobiles)
        
        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(markdown_content)
    
    @classmethod
    def send_workflow_result_notification(cls, instance, result):
        """
        Send workflow result notification to submitter.
        
        Args:
            instance: WorkflowInstance
            result: 'APPROVED', 'REJECTED', or 'WITHDRAWN'
        """
        result_emoji = {
            'APPROVED': '✅',
            'REJECTED': '❌',
            'WITHDRAWN': '↩️'
        }.get(result, '📋')
        
        result_text = {
            'APPROVED': '已通过',
            'REJECTED': '已拒绝',
            'WITHDRAWN': '已撤回'
        }.get(result, result)
        
        title = f"{result_emoji} 审批结果通知"
        
        # Get last task comment if rejected
        last_comment = ""
        if result == 'REJECTED':
            last_task = instance.tasks.filter(status='REJECTED').order_by('-action_time').first()
            if last_task and last_task.comment:
                last_comment = f"\n- **拒绝原因**: {last_task.comment}"
        
        markdown_content = f"""### {title}

您提交的单据审批{result_text}：

- **单据类型**: {instance.workflow.get_business_type_display()}
- **单据编号**: {instance.business_no}
- **金额**: ¥{instance.amount or 0:,.2f}
- **审批结果**: {result_text}{last_comment}
"""
        
        submitter_phone = instance.submitter.phone if hasattr(instance.submitter, 'phone') else None
        at_mobiles = [submitter_phone] if submitter_phone else []
        
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, markdown_content, at_mobiles=at_mobiles)
        
        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(markdown_content)
    
    @classmethod
    def send_custom_notification(cls, title, content, at_mobiles=None, to_users=None):
        """
        Send custom notification to all channels or specific users.
        
        Args:
            title: Notification title
            content: Notification content (markdown supported)
            at_mobiles: List of mobile numbers to @mention (for group notifications)
            to_users: List of User objects or user IDs to send personal messages to
                     If provided, sends personal messages instead of group broadcast
        """
        # If specific users are provided, send personal messages
        if to_users:
            cls.send_personal_notification(to_users, title, content)
            return
        
        # Otherwise, send to group channels
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, content, at_mobiles=at_mobiles)
        
        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(content)
    
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
                logger.error(f"Failed to send WeChat Work personal message: {e}")
        
        # Send via DingTalk work notification
        if dingtalk_user_ids and cls._is_dingtalk_enabled():
            try:
                from apps.core.notification_channels import DingTalkChannel
                dingtalk = DingTalkChannel()
                dingtalk.send_work_notification(dingtalk_user_ids, title, content)
            except Exception as e:
                logger.error(f"Failed to send DingTalk personal message: {e}")
    
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
        
        title = "💰 收款提醒通知"
        lines = [f"### {title}\n"]
        
        if overdue:
            lines.append("#### ⚠️ 已逾期款项\n")
            for p in overdue[:5]:
                lines.append(
                    f"- **{p.sales_order.order_no}** - {p.milestone_name}\n"
                    f"  - 客户: {p.sales_order.customer.name}\n"
                    f"  - 应收: ¥{p.amount_due:,.2f}\n"
                    f"  - 已逾期: {abs(p.days_until_due)} 天\n"
                )
        
        if upcoming:
            lines.append("\n#### 📅 即将到期款项\n")
            for p in upcoming[:5]:
                lines.append(
                    f"- **{p.sales_order.order_no}** - {p.milestone_name}\n"
                    f"  - 客户: {p.sales_order.customer.name}\n"
                    f"  - 应收: ¥{p.amount_due:,.2f}\n"
                    f"  - 到期日: {p.due_date.strftime('%Y-%m-%d')} ({p.days_until_due} 天后)\n"
                )
        
        total_count = len(payment_schedules)
        shown_count = min(len(overdue), 5) + min(len(upcoming), 5)
        if total_count > shown_count:
            lines.append(f"\n... 还有 {total_count - shown_count} 项待收款\n")
        
        total_amount = sum(p.amount_due - p.amount_paid for p in payment_schedules)
        lines.append(f"\n**待收款总额: ¥{total_amount:,.2f}**\n")
        lines.append("\n请及时跟进收款！")
        
        markdown_content = "".join(lines)
        
        # Send to all channels
        if cls._is_dingtalk_enabled():
            DingTalkNotification.send_markdown(title, markdown_content)
        
        if cls._is_wechat_enabled():
            WeChatWorkNotification.send_markdown(markdown_content)