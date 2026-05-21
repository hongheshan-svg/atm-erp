"""
Mixins for views and viewsets.
"""


class UserTrackingMixin:
    """
    Mixin to automatically set created_by and updated_by fields.
    """

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class SoftDeleteMixin:
    """
    Mixin for ViewSet - 优先使用模型自己的软删除实现。
    对不支持软删除的模型，回退到物理删除。
    """

    def perform_destroy(self, instance):
        if hasattr(instance, 'soft_delete'):
            instance.soft_delete()
        elif hasattr(instance, 'is_deleted') and hasattr(instance, 'deleted_at'):
            from django.utils import timezone

            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.save(update_fields=['is_deleted', 'deleted_at'])
        else:
            instance.delete()

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(queryset.model, 'is_deleted'):
            return queryset.filter(is_deleted=False)
        return queryset
