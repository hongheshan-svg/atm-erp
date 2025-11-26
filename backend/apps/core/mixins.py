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
    """
    data_scope_field = 'created_by'  # Can be overridden in view
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return apply_data_scope_filter(
            queryset,
            self.request.user,
            self.data_scope_field
        )


class SoftDeleteMixin:
    """
    Mixin to handle soft delete instead of hard delete.
    """
    def perform_destroy(self, instance):
        if hasattr(instance, 'soft_delete'):
            instance.soft_delete()
        else:
            instance.delete()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Exclude soft-deleted items by default
        if hasattr(queryset.model, 'is_deleted'):
            return queryset.filter(is_deleted=False)
        return queryset

