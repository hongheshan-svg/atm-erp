"""
Mixins for views and viewsets.
"""
from .utils import apply_data_scope_filter


class UserTrackingMixin:
    """
    Mixin to automatically set created_by and updated_by fields.
    """
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class DataScopeMixin:
    """
    Mixin to automatically apply data scope filtering to queryset.
    支持模块级权限控制：特定角色可以查看特定模块的全部数据
    """
    data_scope_field = 'created_by'  # Can be overridden in view
    module_name = None  # 模块名称，用于模块级权限控制

    def get_queryset(self):
        queryset = super().get_queryset()
        # 自动检测模块名称（从app名称推断）
        module = self.module_name
        if not module:
            # 从 queryset.model 的 app_label 获取模块名
            module = getattr(queryset.model, '_meta', None)
            if module:
                module = module.app_label

        return apply_data_scope_filter(
            queryset,
            self.request.user,
            self.data_scope_field,
            module_name=module
        )


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
        # 仍然过滤掉旧的软删除记录（向后兼容）
        if hasattr(queryset.model, 'is_deleted'):
            return queryset.filter(is_deleted=False)
        return queryset
