"""
考勤相关 medium 修复回归测试。

- 加班跨午夜：OvertimeRequestViewSet.perform_create 在 end_time<start_time 时按次日计算，
  避免负工时（修复前 22:00→02:00 得 -20 小时）。
- 请假撤回 cancel 端点的存在性由 `manage.py check` + URL 解析保证（DRF @action 注册），
  其状态流转逻辑与现有 submit/approve/reject 同构，这里只对工时计算做单元断言。
"""

from datetime import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.attendance import OvertimeRequestViewSet

User = get_user_model()
factory = APIRequestFactory()


class _OvertimeStub:
    """记录 perform_create 传给 save() 的 hours，无需触达数据库。"""

    def __init__(self, start_time, end_time):
        self.validated_data = {'start_time': start_time, 'end_time': end_time}
        self.save_kwargs = None

    def save(self, **kwargs):
        self.save_kwargs = kwargs


class OvertimeHoursTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ot_u', password='x', employee_id='ot_u')

    def _hours(self, start, end):
        request = factory.post('/x/')
        request.user = self.user
        viewset = OvertimeRequestViewSet()
        viewset.request = request
        viewset.action = 'create'
        stub = _OvertimeStub(start, end)
        viewset.perform_create(stub)
        return stub.save_kwargs['hours']

    def test_same_day_hours(self):
        self.assertEqual(self._hours(time(18, 0), time(21, 0)), Decimal('3.0'))

    def test_cross_midnight_hours_positive(self):
        # 22:00 → 次日 02:00 = 4 小时（修复前为负数）
        self.assertEqual(self._hours(time(22, 0), time(2, 0)), Decimal('4.0'))
