# Generated manually for permission system redesign
# Data migration to copy User.role FK to User.roles M2M

from django.db import migrations


def migrate_role_to_roles(apps, schema_editor):
    """
    Copy data from User.role (FK) to User.roles (M2M).

    For each user with a role, add that role to the roles M2M field.
    """
    User = apps.get_model('accounts', 'User')

    users_with_role = User.objects.filter(role__isnull=False, is_deleted=False)

    for user in users_with_role:
        # Add the FK role to the M2M roles field
        user.roles.add(user.role)

    print(f"Migrated {users_with_role.count()} users from role FK to roles M2M")


def reverse_migrate_roles_to_role(apps, schema_editor):
    """
    Reverse migration: copy first role from User.roles M2M back to User.role FK.

    If user has multiple roles, only the first one is kept in the FK field.
    """
    User = apps.get_model('accounts', 'User')

    users = User.objects.filter(is_deleted=False)

    for user in users:
        # Get first role from M2M field
        first_role = user.roles.first()
        if first_role:
            user.role = first_role
            user.save(update_fields=['role'])

    print(f"Reversed migration for {users.count()} users")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_add_user_roles_m2m'),
    ]

    operations = [
        migrations.RunPython(
            migrate_role_to_roles,
            reverse_migrate_roles_to_role
        ),
    ]
