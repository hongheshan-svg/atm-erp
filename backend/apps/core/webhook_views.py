"""
Webhook views for managing webhook endpoints and deliveries.
"""
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .webhook import WebhookDelivery, WebhookEndpoint, WebhookService


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """Serializer for webhook endpoints."""
    delivery_count = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'name', 'url', 'secret', 'events', 'headers', 'is_active',
            'max_retries', 'retry_delay', 'timeout', 'created_at', 'updated_at',
            'delivery_count', 'success_rate'
        ]
        extra_kwargs = {
            'secret': {'write_only': True}
        }

    def get_delivery_count(self, obj):
        return obj.deliveries.count()

    def get_success_rate(self, obj):
        total = obj.deliveries.count()
        if total == 0:
            return None
        success = obj.deliveries.filter(status='SUCCESS').count()
        return round(success / total * 100, 1)


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Serializer for webhook deliveries."""
    endpoint_name = serializers.CharField(source='endpoint.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            'id', 'endpoint', 'endpoint_name', 'event_type', 'payload',
            'status', 'status_display', 'response_status', 'response_body',
            'error_message', 'attempts', 'next_retry_at', 'created_at', 'delivered_at'
        ]


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook endpoints."""
    serializer_class = WebhookEndpointSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = WebhookEndpoint.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Send a test webhook to the endpoint."""
        endpoint = self.get_object()

        # Create test delivery
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type='test.ping',
            payload={
                'event': 'test.ping',
                'message': 'This is a test webhook',
                'timestamp': str(timezone.now())
            }
        )

        # Send immediately
        WebhookService.send_delivery(delivery)

        return Response({
            'success': delivery.status == 'SUCCESS',
            'status': delivery.status,
            'response_status': delivery.response_status,
            'error_message': delivery.error_message
        })

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle endpoint active status."""
        endpoint = self.get_object()
        endpoint.is_active = not endpoint.is_active
        endpoint.save()

        return Response({
            'is_active': endpoint.is_active
        })

    @action(detail=False, methods=['get'])
    def event_types(self, request):
        """Get available event types."""
        return Response([
            {'value': code, 'label': label}
            for code, label in WebhookEndpoint.EVENT_TYPES
        ])


class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for webhook deliveries."""
    serializer_class = WebhookDeliverySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = WebhookDelivery.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset().select_related('endpoint')

        # Filter by endpoint
        endpoint_id = self.request.query_params.get('endpoint_id')
        if endpoint_id:
            queryset = queryset.filter(endpoint_id=endpoint_id)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by event type
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed delivery."""
        delivery = self.get_object()

        if delivery.status == 'SUCCESS':
            return Response(
                {'error': 'Cannot retry successful delivery'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset for retry
        delivery.status = 'PENDING'
        delivery.attempts = 0
        delivery.next_retry_at = None
        delivery.save()

        # Send immediately
        WebhookService.send_delivery(delivery)

        return Response({
            'success': delivery.status == 'SUCCESS',
            'status': delivery.status
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get delivery statistics."""
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        days = int(request.query_params.get('days', 7))
        cutoff = timezone.now() - timedelta(days=days)

        queryset = WebhookDelivery.objects.filter(created_at__gte=cutoff)

        stats = {
            'total': queryset.count(),
            'success': queryset.filter(status='SUCCESS').count(),
            'failed': queryset.filter(status='FAILED').count(),
            'pending': queryset.filter(status__in=['PENDING', 'RETRYING']).count(),
            'by_event': list(queryset.values('event_type').annotate(count=Count('id'))),
            'by_endpoint': list(queryset.values('endpoint__name').annotate(count=Count('id'))),
        }

        return Response(stats)


# Import timezone for test action
from django.utils import timezone
