"""
Mixins for views and viewsets.
"""


class UserTrackingMixin:
    """
    Mixin to automatically set created_by and updated_by fields.

    仅在目标模型确实存在对应字段时才注入，避免对不继承 BaseModel
    的模型(如 User/Role/Department)注入 created_by/updated_by 导致
    `TypeError: Model() got unexpected keyword arguments`。
    """

    @staticmethod
    def _model_field_names(serializer):
        model = getattr(getattr(serializer, 'Meta', None), 'model', None)
        if model is None:
            return set()
        return {f.name for f in model._meta.get_fields()}

    def perform_create(self, serializer):
        fields = self._model_field_names(serializer)
        kwargs = {}
        if 'created_by' in fields:
            kwargs['created_by'] = self.request.user
        if 'updated_by' in fields:
            kwargs['updated_by'] = self.request.user
        serializer.save(**kwargs)

    def perform_update(self, serializer):
        fields = self._model_field_names(serializer)
        kwargs = {}
        if 'updated_by' in fields:
            kwargs['updated_by'] = self.request.user
        serializer.save(**kwargs)


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
