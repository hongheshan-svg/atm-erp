"""
H13 回归测试：self 数据范围不应误伤“自管可见性”的 OA 协同 ViewSet。

根因：apply_scope_filter('self') 硬编码 created_by=user，被 PermissionMixin.get_queryset
前置到公告/日程/会议/会话等协同 ViewSet 上，把全员公告、公开日程、被邀会议、他人拉入的群聊
对 self 范围常见角色（员工/销售/会计等）错误隐藏。

修复：PermissionMixin 增加 skip_data_scope 开关；置 True 的 ViewSet 跳过通用数据范围过滤，
由其自身 get_queryset / 按动作的受众过滤权威决定可见性。

验证方式：用真实 ViewSet/模型 + APIRequestFactory，直接检查 get_queryset() 编译出的 SQL
是否带 created_by 过滤（不创建数据行，避免无关必填字段干扰）；并确认 6 个协同 ViewSet 均已置位。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import viewsets
from rest_framework.test import APIRequestFactory

from apps.accounts.attendance import AttendanceRecord
from apps.accounts.models import Role
from apps.core.permission_mixin import PermissionMixin
from apps.core.permission_models_new import DataScope
from apps.projects.models import Project

User = get_user_model()
factory = APIRequestFactory()


class _ScopedVS(PermissionMixin, viewsets.ModelViewSet):
    """对照：默认 skip_data_scope=False，受通用数据范围过滤。"""

    permission_module = 'projects'
    permission_resource = 'project'
    queryset = Project.objects.all()


class _SkipVS(_ScopedVS):
    """修复：跳过通用数据范围过滤。"""

    skip_data_scope = True


class H13SkipDataScopeTest(TestCase):
    def setUp(self):
        cache.clear()
        self.emp = User.objects.create_user(username='h13_emp', password='x', employee_id='h13_emp')
        # 员工角色：全局 self 数据范围（module='' 命中所有模块）
        role = Role.objects.create(name='h13_emp_role', code='h13_emp_role')
        DataScope.objects.create(role=role, module='', scope_type='self')
        self.emp.role = role
        self.emp.save()

    def _where_clause(self, viewset_cls):
        # 只取 WHERE 之后部分：created_by_id 始终出现在 SELECT 列里，
        # 必须看 WHERE 子句才能区分“是否按 created_by 过滤”。
        request = factory.get('/x/')
        request.user = self.emp
        viewset = viewset_cls()
        viewset.request = request
        viewset.action = 'list'
        sql = str(viewset.get_queryset().query)
        return sql.split('WHERE', 1)[1] if 'WHERE' in sql else ''

    def test_self_scope_applies_created_by_filter_without_skip(self):
        # 对照：self 范围 + 未跳过 → WHERE 带 created_by 过滤（他人创建的数据被隐藏）
        self.assertIn('created_by', self._where_clause(_ScopedVS))

    def test_skip_data_scope_drops_created_by_filter(self):
        # 修复：self 范围 + 跳过 → WHERE 不再带 created_by 过滤（共享/公开/被邀数据可见，审计 H13）
        self.assertNotIn('created_by', self._where_clause(_SkipVS))

    def test_collaboration_viewsets_have_flag(self):
        from apps.core.announcement import AnnouncementViewSet
        from apps.core.schedule import MeetingRoomViewSet, MeetingViewSet, ScheduleViewSet

        for vs in (
            AnnouncementViewSet,
            ScheduleViewSet,
            MeetingRoomViewSet,
            MeetingViewSet,
        ):
            self.assertTrue(vs.skip_data_scope, f'{vs.__name__} 应 skip_data_scope=True (H13)')


class _AttnUserVS(PermissionMixin, viewsets.ModelViewSet):
    """归属字段为 user（修复后）。"""

    permission_module = 'accounts'
    permission_resource = 'attendance_record'
    data_scope_user_field = 'user'
    queryset = AttendanceRecord.objects.all()


class _AttnDefaultVS(PermissionMixin, viewsets.ModelViewSet):
    """对照：默认按 created_by（错误地以导入者为归属）。"""

    permission_module = 'accounts'
    permission_resource = 'attendance_record'
    queryset = AttendanceRecord.objects.all()


class H14AttendanceSelfScopeTest(TestCase):
    """H14：考勤/请假/加班 self 范围应按归属字段 user 过滤，而非 created_by（导入者=管理员）。"""

    def setUp(self):
        cache.clear()
        self.emp = User.objects.create_user(username='h14_emp', password='x', employee_id='h14_emp')
        role = Role.objects.create(name='h14_emp_role', code='h14_emp_role')
        DataScope.objects.create(role=role, module='', scope_type='self')
        self.emp.role = role
        self.emp.save()

    def _where_clause(self, viewset_cls):
        request = factory.get('/x/')
        request.user = self.emp
        viewset = viewset_cls()
        viewset.request = request
        viewset.action = 'list'
        sql = str(viewset.get_queryset().query)
        return sql.split('WHERE', 1)[1] if 'WHERE' in sql else ''

    def test_self_scope_filters_by_user_field(self):
        # 修复：data_scope_user_field='user' → 按 user_id 过滤，不再按 created_by（审计 H14）
        where = self._where_clause(_AttnUserVS)
        self.assertIn('user_id', where)
        self.assertNotIn('created_by', where)

    def test_default_owner_field_unchanged(self):
        # 回归保护：未配置时仍按 created_by 过滤（不影响其它业务 ViewSet）
        self.assertIn('created_by', self._where_clause(_AttnDefaultVS))

    def test_attendance_viewsets_use_user_field(self):
        from apps.accounts.attendance import (
            AttendanceRecordViewSet,
            LeaveRequestViewSet,
            OvertimeRequestViewSet,
        )

        for vs in (AttendanceRecordViewSet, LeaveRequestViewSet, OvertimeRequestViewSet):
            self.assertEqual(vs.data_scope_user_field, 'user', f'{vs.__name__} 应按 user 归属 (H14)')
