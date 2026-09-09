from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', '管理员'
        MANAGER = 'manager', '项目经理'
        PURCHASER = 'purchaser', '采购'
        WAREHOUSE = 'warehouse', '仓库'
        FINANCE = 'finance', '财务'
        MEMBER = 'member', '成员'

    groups = None
    user_permissions = None
    display_name = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    hourly_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    management_reports = models.BooleanField(default=False)

    class Meta:
        db_table = 'lean_user'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(hourly_cost__gte=0), name='lean_nonnegative_hourly_cost'),
            models.CheckConstraint(
                condition=models.Q(role__in=['admin', 'manager', 'purchaser', 'warehouse', 'finance', 'member']),
                name='lean_fixed_role',
            ),
        ]
