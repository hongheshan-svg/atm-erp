from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.core.permission_models_new import DataScope, Permission, RolePermission
from apps.core.permission_service import (
    invalidate_all_permission_caches,
    on_role_permission_change,
    on_user_role_change,
)

from .models import Role, User


@receiver(post_save, sender=User)
def clear_user_permission_cache_on_user_save(sender, instance, **kwargs):
    on_user_role_change(instance)


@receiver(m2m_changed, sender=User.roles.through)
def clear_user_permission_cache_on_roles_change(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return

    if reverse:
        if isinstance(instance, Role):
            on_role_permission_change(instance)
        else:
            for role in model.objects.filter(pk__in=pk_set or []):
                on_role_permission_change(role)
        return

    on_user_role_change(instance)


@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
def clear_user_permission_cache_on_role_change(sender, instance, **kwargs):
    on_role_permission_change(instance)


@receiver(post_save, sender=Permission)
@receiver(post_delete, sender=Permission)
@receiver(post_save, sender=RolePermission)
@receiver(post_delete, sender=RolePermission)
@receiver(post_save, sender=DataScope)
@receiver(post_delete, sender=DataScope)
def clear_permission_caches_on_policy_change(sender, instance, **kwargs):
    invalidate_all_permission_caches()


@receiver(m2m_changed, sender=Role.permissions_new.through)
@receiver(m2m_changed, sender=DataScope.custom_departments.through)
def clear_permission_caches_on_policy_m2m_change(sender, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        invalidate_all_permission_caches()
