"""
P1-2 回归测试：scheduling.KanbanView 的质量指标必须来自真实 QualityInspection 聚合，
而非旧代码里硬编码的 pass_rate=98.5 / defects_today=2 假数据。

口径与 apps/production/kanban.py 的 ProductionKanbanView 一致：
- 使用 QualityInspection.result 的真实取值 PASS / FAIL（RESULT_CHOICES 为 PASS/FAIL/CONDITIONAL）
- 合格率 = PASS /（PASS + FAIL），仅计入已判定的检验
- 今日缺陷数 = 今日 result='FAIL' 的检验数
"""

from datetime import date, timedelta

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.masterdata.models import Customer
from apps.production.models import QualityInspection
from apps.production.scheduling import KanbanView
from apps.projects.models import Project


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class KanbanQualityMetricsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='kanban_qa', employee_id='KQA1', is_staff=True, is_superuser=True
        )
        self.customer = Customer.objects.create(code='CUST-KQA', name='看板测试客户')
        self.project = Project.objects.create(
            code='PRJ-KQA',
            name='看板测试项目',
            customer=self.customer,
            manager=self.user,
            start_date='2026-07-01',
            end_date='2026-12-31',
        )
        self.factory = APIRequestFactory()

    def _insp(self, no, result, when):
        return QualityInspection.objects.create(
            project=self.project,
            inspection_no=no,
            title='质检',
            result=result,
            inspection_date=when,
        )

    def _get_quality(self):
        request = self.factory.get('/api/production/kanban/')
        force_authenticate(request, user=self.user)
        response = KanbanView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        return response.data['quality']

    def test_pass_rate_and_defects_are_real_aggregates(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        # 今日：3 PASS、1 FAIL、1 CONDITIONAL
        self._insp('QI-T1', 'PASS', today)
        self._insp('QI-T2', 'PASS', today)
        self._insp('QI-T3', 'PASS', today)
        self._insp('QI-T4', 'FAIL', today)
        self._insp('QI-T5', 'CONDITIONAL', today)
        # 昨日（用于验证按天限定，不应计入今日口径）：1 PASS、1 FAIL
        self._insp('QI-Y1', 'PASS', yesterday)
        self._insp('QI-Y2', 'FAIL', yesterday)

        quality = self._get_quality()

        # 今日质检总数（含 CONDITIONAL），排除昨日
        self.assertEqual(quality['inspections_today'], 5)
        # 今日缺陷 = 今日 FAIL 数
        self.assertEqual(quality['defects_today'], 1)
        # 合格率 = PASS /(PASS+FAIL) = 3/4 = 75.0；CONDITIONAL 不进分母
        self.assertEqual(quality['pass_rate'], 75.0)
        # 旧的假数据已被移除
        self.assertNotEqual(quality['pass_rate'], 98.5)
        self.assertNotEqual(quality['defects_today'], 2)

    def test_no_inspections_returns_zero_not_fake_constant(self):
        quality = self._get_quality()
        self.assertEqual(quality['inspections_today'], 0)
        self.assertEqual(quality['defects_today'], 0)
        # 无已判定检验时合格率为 0，而非硬编码 98.5
        self.assertEqual(quality['pass_rate'], 0)
