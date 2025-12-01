"""
Celery tasks for inventory app.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import F
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_low_stock_levels():
    """
    Check for low stock levels and send alerts.
    Runs daily at 8 AM.
    """
    from .models import Stock
    from apps.accounts.models import User
    from apps.core.notification_service import NotificationService
    
    low_stocks = Stock.objects.select_related('item', 'warehouse').filter(
        qty_on_hand__lt=F('item__min_stock'),
        item__min_stock__gt=0
    )
    
    if not low_stocks.exists():
        return "No low stock items"
    
    # Build alert data
    low_stock_items = []
    message_lines = ["以下物料库存不足:\n"]
    
    for stock in low_stocks:
        message_lines.append(
            f"- {stock.item.sku} {stock.item.name} | "
            f"仓库: {stock.warehouse.name} | "
            f"当前: {stock.qty_on_hand} | "
            f"最小: {stock.item.min_stock}"
        )
        low_stock_items.append({
            'sku': stock.item.sku,
            'name': stock.item.name,
            'warehouse': stock.warehouse.name,
            'qty_on_hand': float(stock.qty_on_hand),
            'min_stock': float(stock.item.min_stock)
        })
    
    message = "\n".join(message_lines)
    
    # Send email to admins
    admin_emails = list(User.objects.filter(
        is_staff=True, 
        is_active=True
    ).exclude(email='').values_list('email', flat=True))
    
    if admin_emails:
        try:
            send_mail(
                subject='ERP系统 - 库存预警',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    # Send to DingTalk/WeChat Work
    try:
        NotificationService.send_stock_alert(low_stock_items)
    except Exception as e:
        logger.error(f"Failed to send external notification: {e}")
    
    return f"Sent low stock alert for {low_stocks.count()} items"


@shared_task
def check_expiring_batches(days=30):
    """
    Check for batches expiring within specified days.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .batch_models import Batch
    from apps.accounts.models import User
    from apps.core.notification_service import NotificationService
    
    expiry_date = timezone.now().date() + timedelta(days=days)
    
    expiring_batches = Batch.objects.select_related('item', 'warehouse').filter(
        expiry_date__lte=expiry_date,
        expiry_date__gte=timezone.now().date(),
        qty_on_hand__gt=0,
        is_deleted=False
    ).order_by('expiry_date')
    
    if not expiring_batches.exists():
        return "No expiring batches"
    
    # Build notification
    items = []
    for batch in expiring_batches:
        items.append({
            'sku': batch.item.sku,
            'name': batch.item.name,
            'warehouse': batch.warehouse.name,
            'batch_no': batch.batch_no,
            'qty_on_hand': float(batch.qty_on_hand),
            'expiry_date': batch.expiry_date.strftime('%Y-%m-%d'),
            'days_to_expiry': batch.days_to_expiry
        })
    
    # Send notification
    title = "⚠️ 批次即将过期提醒"
    content = f"### {title}\n\n以下批次将在 {days} 天内过期：\n\n"
    
    for item in items[:10]:
        content += (
            f"- **{item['sku']}** {item['name']}\n"
            f"  - 批次: {item['batch_no']}\n"
            f"  - 数量: {item['qty_on_hand']}\n"
            f"  - 过期日期: {item['expiry_date']} ({item['days_to_expiry']}天后)\n"
        )
    
    try:
        NotificationService.send_custom_notification(title, content)
    except Exception as e:
        logger.error(f"Failed to send expiry notification: {e}")
    
    return f"Found {expiring_batches.count()} expiring batches"

