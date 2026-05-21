"""
权限配置说明文件

权限系统已统一迁移到：
- 权限树种子数据：management/commands/init_permissions.py
- 角色与权限分配：management/commands/init_roles.py
- 运行时权限服务：permission_service.py
- ViewSet 统一 Mixin：permission_mixin.py

本文件仅保留 is_finance_allowed 工具函数供外部调用。
"""

from apps.core.permission_service import get_user_permissions


def is_finance_allowed(user) -> bool:
    """检查用户是否有财务模块访问权限"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_permissions = get_user_permissions(user)
    return any(code == 'finance' or code.startswith('finance:') for code in user_permissions)
