"""Fixed identity separation, independent of how many roles an account holds."""

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.permissions import ADMIN, has_role


def independent_approval(user, applicant_ids, reason):
    if user.pk not in applicant_ids:
        return False
    if not has_role(user, ADMIN):
        raise PermissionDenied('申请人不能审批自己的单据，兼任角色也不能绕过；请交由其他有权限的人员审批。')
    if not reason.strip():
        raise ValidationError({'reason': '管理员处理本人申请时，必须填写例外审批原因并保留审计。'})
    return True
