"""
Notification service for system-wide notifications
"""
from django.core.mail import send_mail
from django.conf import settings
from .models import SystemNotification
from celery import shared_task


class NotificationService:
    """Service for creating and sending notifications"""
    
    @staticmethod
    def create_notification(user, title, message, notification_type='INFO'):
        """Create a system notification for a user"""
        notification = SystemNotification.objects.create(
            user=user,
            type=notification_type,
            title=title,
            message=message
        )
        
        # Send real-time WebSocket notification
        try:
            from .websocket_utils import WebSocketNotifier
            WebSocketNotifier.send_notification_to_user(
                user.id,
                {
                    'id': notification.id,
                    'type': notification_type,
                    'title': title,
                    'message': message,
                    'created_at': notification.created_at.isoformat(),
                    'is_read': False
                }
            )
        except Exception as e:
            # Don't fail if WebSocket send fails
            print(f"WebSocket notification failed: {e}")
        
        return notification
    
    @staticmethod
    def notify_users(users, title, message, notification_type='INFO', send_email=False):
        """Notify multiple users"""
        notifications = []
        for user in users:
            notif = NotificationService.create_notification(
                user, title, message, notification_type
            )
            notifications.append(notif)
            
            if send_email and user.email:
                send_email_notification.delay(user.email, title, message)
        
        return notifications
    
    @staticmethod
    def mark_as_read(notification_id, user):
        """Mark notification as read"""
        from django.utils import timezone
        notification = SystemNotification.objects.get(id=notification_id, user=user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return notification


@shared_task
def send_email_notification(to_email, subject, message):
    """Celery task to send email notifications"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


@shared_task
def check_low_stock_and_notify():
    """Check for low stock items and notify relevant users"""
    from apps.inventory.models import Stock
    from apps.accounts.models import User
    from django.db.models import F
    
    low_stock_items = Stock.objects.filter(
        qty_on_hand__lte=F('item__min_stock')
    ).select_related('item', 'warehouse')
    
    if low_stock_items.exists():
        # Notify procurement team
        procurement_users = User.objects.filter(
            role__name='Buyer'
        )
        
        message = f"发现 {low_stock_items.count()} 个库存不足的物料，请及时补货。"
        
        NotificationService.notify_users(
            procurement_users,
            '库存预警',
            message,
            'WARNING',
            send_email=True
        )


@shared_task
def check_overdue_ar_and_notify():
    """Check overdue accounts receivable and notify"""
    from apps.finance.models import AccountReceivable
    from apps.accounts.models import User
    from datetime import date
    
    overdue_ar = AccountReceivable.objects.filter(
        due_date__lt=date.today(),
        status__in=['PENDING', 'PARTIAL']
    )
    
    if overdue_ar.exists():
        # Notify finance team
        finance_users = User.objects.filter(
            department__name='Finance Department'
        )
        
        total_overdue = sum(ar.amount_due - ar.amount_paid for ar in overdue_ar)
        message = f"发现 {overdue_ar.count()} 笔逾期应收账款，总金额 ${total_overdue:,.2f}"
        
        NotificationService.notify_users(
            finance_users,
            '应收账款逾期提醒',
            message,
            'WARNING',
            send_email=True
        )

