from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', '管理员'
        MANAGER = 'manager', '项目经理'
        PRODUCTION_MANAGER = 'production_manager', '生产经理'
        SALES_MANAGER = 'sales_manager', '销售经理'
        PURCHASE_MANAGER = 'purchase_manager', '采购经理'
        PURCHASER = 'purchaser', '采购员'
        WAREHOUSE = 'warehouse', '仓管'
        FINANCE = 'finance', '财务'
        MECHANICAL_ENGINEER = 'mechanical_engineer', '机械工程师'
        ELECTRICAL_ENGINEER = 'electrical_engineer', '电气工程师'
        MEMBER = 'member', '普通成员'

    groups = None
    user_permissions = None
    display_name = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    additional_roles = ArrayField(models.CharField(max_length=20, choices=Role.choices), default=list, blank=True)
    hourly_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    management_reports = models.BooleanField(default=False)

    class Meta:
        db_table = 'lean_user'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(hourly_cost__gte=0), name='lean_nonnegative_hourly_cost'),
            models.CheckConstraint(
                condition=models.Q(
                    role__in=[
                        'admin',
                        'manager',
                        'production_manager',
                        'sales_manager',
                        'purchase_manager',
                        'purchaser',
                        'warehouse',
                        'finance',
                        'mechanical_engineer',
                        'electrical_engineer',
                        'member',
                    ]
                ),
                name='lean_fixed_role',
            ),
        ]
