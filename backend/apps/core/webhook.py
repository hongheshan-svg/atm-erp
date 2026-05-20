"""
Webhook service for third-party system integration.
"""
import hashlib
import hmac
import json
import logging

import requests
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookEndpoint(models.Model):
    """
    Webhook endpoint configuration.
    """
    EVENT_TYPES = [
        ('project.created', '项目创建'),
        ('project.updated', '项目更新'),
        ('project.completed', '项目完成'),
        ('order.created', '订单创建'),
        ('order.confirmed', '订单确认'),
        ('order.completed', '订单完成'),
        ('inventory.low_stock', '库存预警'),
        ('inventory.movement', '库存变动'),
        ('approval.submitted', '审批提交'),
        ('approval.approved', '审批通过'),
        ('approval.rejected', '审批拒绝'),
        ('payment.received', '收款'),
        ('payment.made', '付款'),
    ]

    name = models.CharField(max_length=100, verbose_name='名称')
    url = models.URLField(verbose_name='回调URL')
    secret = models.CharField(max_length=200, blank=True, verbose_name='签名密钥')
    events = models.JSONField(default=list, verbose_name='订阅事件')
    headers = models.JSONField(default=dict, blank=True, verbose_name='自定义请求头')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    # Retry settings
    max_retries = models.IntegerField(default=3, verbose_name='最大重试次数')
    retry_delay = models.IntegerField(default=60, verbose_name='重试间隔(秒)')
    timeout = models.IntegerField(default=30, verbose_name='超时时间(秒)')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'webhook_endpoint'
        verbose_name = 'Webhook端点'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.url})"


class WebhookDelivery(models.Model):
    """
    Webhook delivery log.
    """
    STATUS_CHOICES = [
        ('PENDING', '待发送'),
        ('SUCCESS', '成功'),
        ('FAILED', '失败'),
        ('RETRYING', '重试中'),
    ]

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name='deliveries',
        verbose_name='端点'
    )
    event_type = models.CharField(max_length=50, verbose_name='事件类型')
    payload = models.JSONField(verbose_name='请求数据')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    response_status = models.IntegerField(null=True, blank=True, verbose_name='响应状态码')
    response_body = models.TextField(blank=True, verbose_name='响应内容')
    error_message = models.TextField(blank=True, verbose_name='错误信息')

    attempts = models.IntegerField(default=0, verbose_name='尝试次数')
    next_retry_at = models.DateTimeField(null=True, blank=True, verbose_name='下次重试时间')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='送达时间')

    class Meta:
        db_table = 'webhook_delivery'
        verbose_name = 'Webhook投递记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
        ]

    def __str__(self):
        return f"{self.endpoint.name} - {self.event_type} - {self.status}"


class WebhookService:
    """
    Service for sending webhooks.
    """

    @classmethod
    def trigger_event(cls, event_type, data, related_object=None):
        """
        Trigger a webhook event.
        
        Args:
            event_type: Event type string (e.g., 'project.created')
            data: Event data dict
            related_object: Optional related Django model instance
        """
        # Find active endpoints subscribed to this event
        endpoints = WebhookEndpoint.objects.filter(
            is_active=True,
            events__contains=[event_type]
        )

        if not endpoints.exists():
            logger.debug(f"No webhook endpoints for event: {event_type}")
            return

        # Build payload
        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'data': data
        }

        if related_object:
            payload['object_type'] = related_object.__class__.__name__
            payload['object_id'] = getattr(related_object, 'id', None)

        # Create delivery records
        for endpoint in endpoints:
            WebhookDelivery.objects.create(
                endpoint=endpoint,
                event_type=event_type,
                payload=payload
            )

        # Trigger async delivery
        from celery import current_app
        try:
            current_app.send_task('apps.core.tasks.process_webhook_deliveries')
        except Exception as e:
            logger.warning(f"Could not queue webhook task: {e}")
            # Fallback to sync delivery
            cls.process_pending_deliveries()

    @classmethod
    def process_pending_deliveries(cls):
        """
        Process pending webhook deliveries.
        """
        pending = WebhookDelivery.objects.filter(
            status__in=['PENDING', 'RETRYING'],
            attempts__lt=models.F('endpoint__max_retries')
        ).select_related('endpoint')

        # Filter by retry time
        now = timezone.now()
        pending = pending.filter(
            models.Q(next_retry_at__isnull=True) |
            models.Q(next_retry_at__lte=now)
        )

        for delivery in pending[:100]:  # Process in batches
            cls.send_delivery(delivery)

    @classmethod
    def send_delivery(cls, delivery):
        """
        Send a single webhook delivery.
        """
        endpoint = delivery.endpoint

        try:
            # Build headers
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Event': delivery.event_type,
                'X-Webhook-Delivery': str(delivery.id),
                'X-Webhook-Timestamp': timezone.now().isoformat(),
            }

            # Add custom headers
            if endpoint.headers:
                headers.update(endpoint.headers)

            # Add signature if secret is configured
            payload_json = json.dumps(delivery.payload, default=str)
            if endpoint.secret:
                signature = cls.generate_signature(payload_json, endpoint.secret)
                headers['X-Webhook-Signature'] = signature

            # Send request
            response = requests.post(
                endpoint.url,
                data=payload_json,
                headers=headers,
                timeout=endpoint.timeout
            )

            delivery.attempts += 1
            delivery.response_status = response.status_code
            delivery.response_body = response.text[:5000]  # Limit response size

            if 200 <= response.status_code < 300:
                delivery.status = 'SUCCESS'
                delivery.delivered_at = timezone.now()
            else:
                cls._handle_failure(delivery, f"HTTP {response.status_code}")

        except requests.Timeout:
            delivery.attempts += 1
            cls._handle_failure(delivery, "Request timeout")
        except requests.RequestException as e:
            delivery.attempts += 1
            cls._handle_failure(delivery, str(e))
        except Exception as e:
            delivery.attempts += 1
            cls._handle_failure(delivery, f"Unexpected error: {e}")
            logger.exception(f"Webhook delivery error: {e}")

        delivery.save()

    @classmethod
    def _handle_failure(cls, delivery, error_message):
        """
        Handle delivery failure.
        """
        delivery.error_message = error_message

        if delivery.attempts >= delivery.endpoint.max_retries:
            delivery.status = 'FAILED'
        else:
            delivery.status = 'RETRYING'
            delivery.next_retry_at = timezone.now() + timezone.timedelta(
                seconds=delivery.endpoint.retry_delay * delivery.attempts
            )

    @classmethod
    def generate_signature(cls, payload, secret):
        """
        Generate HMAC signature for payload.
        """
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def verify_signature(cls, payload, signature, secret):
        """
        Verify webhook signature.
        """
        expected = cls.generate_signature(payload, secret)
        return hmac.compare_digest(expected, signature)


# Convenience functions for common events
def trigger_project_event(event_type, project):
    """Trigger project-related webhook."""
    WebhookService.trigger_event(event_type, {
        'id': project.id,
        'code': project.code,
        'name': project.name,
        'status': project.status,
        'manager': project.manager.username if project.manager else None,
    }, project)


def trigger_order_event(event_type, order, order_type='sales'):
    """Trigger order-related webhook."""
    WebhookService.trigger_event(event_type, {
        'id': order.id,
        'order_no': order.order_no,
        'type': order_type,
        'total_amount': str(order.total_amount),
        'status': order.status,
    }, order)


def trigger_approval_event(event_type, instance):
    """Trigger approval-related webhook."""
    WebhookService.trigger_event(event_type, {
        'id': instance.id,
        'business_type': instance.business_type,
        'business_no': instance.business_no,
        'status': instance.status,
        'submitter': instance.submitter.username,
        'amount': str(instance.amount) if instance.amount else None,
    }, instance)
