"""
报工 -> 人工成本 断链整改回归测试

覆盖：
- 主报工动作（ProductionLogViewSet.create）在回写工时后，按 `工时 × 工种费率`
  生成一条 ProjectCostDetail（DIRECT_LABOR）成本明细并挂到项目上。
- 幂等：同一报工重复登记不产生重复成本明细。
- 无项目 -> 无操作（no-op），且报工本身依旧成功。
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.masterdata.models import Customer
from apps.production.labor_cost import post_labor_cost, resolve_work_type
from apps.production.models import (
    ProductionLog,
    ProductionPlan,
    ProductionPlanProcess,
    ProductionProcess,
)
from apps.production.views import ProductionLogViewSet
from apps.projects.advanced_cost_tracking import LaborRateStandard, ProjectCostDetail
from apps.projects.models import Project


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ReportLaborCostTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='mes_op', employee_id='MES1', is_staff=True, is_superuser=True
        )
        self.customer = Customer.objects.create(code='CUST-MES', name='报工成本客户')
        self.project = Project.objects.create(
            code='PRJ-MES',
            name='报工成本项目',
            customer=self.customer,
            manager=self.user,
            start_date='2026-07-01',
            end_date='2026-12-31',
        )
        self.process = ProductionProcess.objects.create(
            project=self.project,
            process_no='OP-10',
            name='总装',
            process_type='ASSEMBLY',  # -> ASSEMBLY_MECHANICAL 机械装配
            sequence=1,
        )
        self.plan = ProductionPlan.objects.create(
            project=self.project,
            plan_no='PP-MES-1',
            title='报工成本计划',
            planned_start=date(2026, 7, 1),
            planned_end=date(2026, 7, 31),
            status='IN_PROGRESS',
        )
        self.plan_process = ProductionPlanProcess.objects.create(
            plan=self.plan,
            process=self.process,
            planned_start=timezone.now(),
            planned_end=timezone.now(),
            status='IN_PROGRESS',
        )
        # 机械装配 工种费率标准：100 元/小时
        self.rate = LaborRateStandard.objects.create(
            work_type='ASSEMBLY_MECHANICAL',
            standard_rate=Decimal('100.00'),
            effective_from=date(2026, 1, 1),
        )
        self.factory = APIRequestFactory()

    def _report(self, work_hours, progress=50):
        """通过真实报工动作（ViewSet.create）提交一次报工。"""
        payload = {
            'plan_process': self.plan_process.id,
            'log_date': '2026-07-02',
            'operator': self.user.id,
            'work_hours': str(work_hours),
            'work_content': '总装报工',
            'progress_percent': progress,
        }
        request = self.factory.post('/api/production/logs/', payload, format='json')
        force_authenticate(request, user=self.user)
        response = ProductionLogViewSet.as_view({'post': 'create'})(request)
        return response

    def test_report_generates_labor_cost_detail(self):
        """报工 8 小时 -> 生成一条 800.00 的 DIRECT_LABOR 成本明细。"""
        response = self._report(Decimal('8'))
        self.assertEqual(response.status_code, 201, response.data)

        log = ProductionLog.objects.get(plan_process=self.plan_process)
        # 工时依旧被回写
        self.plan_process.refresh_from_db()
        self.assertEqual(self.plan_process.actual_hours, Decimal('8.00'))

        details = ProjectCostDetail.objects.filter(
            project=self.project, cost_element='DIRECT_LABOR'
        )
        self.assertEqual(details.count(), 1)
        detail = details.first()
        self.assertEqual(detail.actual_amount, Decimal('800.00'))  # 8 * 100
        self.assertEqual(detail.source_type, 'TIMESHEET')
        self.assertEqual(detail.source_doc_type, 'ProductionLog')
        self.assertEqual(detail.source_doc_id, log.id)
        self.assertEqual(detail.project_phase, 'PRODUCTION')
        self.assertEqual(detail.unit_cost, Decimal('100.00'))
        self.assertEqual(detail.quantity, Decimal('8'))

    def test_labor_cost_is_idempotent_for_same_report(self):
        """同一报工重复登记不产生重复成本（幂等）。"""
        log = ProductionLog.objects.create(
            plan_process=self.plan_process,
            log_date=date(2026, 7, 2),
            operator=self.user,
            work_hours=Decimal('4'),
            work_content='总装报工',
            progress_percent=30,
        )
        work_type = resolve_work_type(self.process.process_type)

        first = post_labor_cost(log, log.work_hours, work_type, self.user, self.project)
        second = post_labor_cost(log, log.work_hours, work_type, self.user, self.project)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            ProjectCostDetail.objects.filter(
                project=self.project, cost_element='DIRECT_LABOR'
            ).count(),
            1,
        )
        self.assertEqual(first.actual_amount, Decimal('400.00'))  # 4 * 100

    def test_no_project_is_noop_but_report_succeeds(self):
        """无项目 -> 不生成成本明细（no-op），报工记录本身仍然存在。"""
        log = ProductionLog.objects.create(
            plan_process=self.plan_process,
            log_date=date(2026, 7, 2),
            operator=self.user,
            work_hours=Decimal('5'),
            work_content='总装报工',
            progress_percent=20,
        )
        work_type = resolve_work_type(self.process.process_type)

        result = post_labor_cost(log, log.work_hours, work_type, self.user, project=None)

        self.assertIsNone(result)
        self.assertEqual(ProjectCostDetail.objects.count(), 0)
        # 报工记录未受影响
        self.assertTrue(ProductionLog.objects.filter(pk=log.pk).exists())

    def test_default_rate_used_when_no_rate_standard(self):
        """无对应工种费率标准时回退默认费率（默认 0）；仍生成一条链接明细。"""
        self.rate.delete()
        log = ProductionLog.objects.create(
            plan_process=self.plan_process,
            log_date=date(2026, 7, 2),
            operator=self.user,
            work_hours=Decimal('6'),
            work_content='总装报工',
            progress_percent=10,
        )
        work_type = resolve_work_type(self.process.process_type)

        detail = post_labor_cost(log, log.work_hours, work_type, self.user, self.project)

        self.assertIsNotNone(detail)
        self.assertEqual(detail.unit_cost, Decimal('0'))
        self.assertEqual(detail.actual_amount, Decimal('0.00'))
        self.assertEqual(detail.cost_element, 'DIRECT_LABOR')
