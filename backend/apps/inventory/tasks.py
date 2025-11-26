"""
Celery tasks for inventory app.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import F


@shared_task
def check_low_stock_levels():
    """
    Check for low stock levels and send alerts.
    Runs daily at 8 AM.
    """
    from .models import Stock
    from apps.accounts.models import User
    
    low_stocks = Stock.objects.select_related('item', 'warehouse').filter(
        qty_on_hand__lt=F('item__min_stock'),
        item__min_stock__gt=0
    )
    
    if not low_stocks.exists():
        return "No low stock items"
    
    # Build alert message
    message_lines = ["以下物料库存不足:\n"]
    for stock in low_stocks:
        message_lines.append(
            f"- {stock.item.sku} {stock.item.name} | "
            f"仓库: {stock.warehouse.name} | "
            f"当前: {stock.qty_on_hand} | "
            f"最小: {stock.item.min_stock}"
        )
    
    message = "\n".join(message_lines)
    
    # Send email to admins
    admin_emails = list(User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True))
    
    if admin_emails:
        send_mail(
            subject='ERP系统 - 库存预警',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=True,
        )
    
    return f"Sent low stock alert for {low_stocks.count()} items"

