"""APS 有限产能排产回归测试。

覆盖把 APS 从"玩具排程(hours=qty×1，忽略工艺路线，策略字段闲置)"升级为读取工艺路线
标准工时的有限产能排程后的关键行为：

- 工时来自工艺路线各工序的 standard_hours(+setup)，而非 quantity×1。
- 两个工单叠加超过工作中心日产能时，后者顺延到下一个工作日。
- 高优先级 / 早需求日期的工单先排。
- 各工作中心利用率为真实值且落在 [0, 100]。
- FiniteCapacityScheduler：scheduling_strategy 真正生效 + avg_utilization 真实计算。
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.masterdata.models import Item
from apps.production.aps import APSScheduleTask, APSService, ScheduleOrder
from apps.production.finite_capacity import (
    FiniteCapacityPlan,
    FiniteCapacityScheduler,
    ScheduledTask,
)
from apps.production.routing import RoutingOperation, RoutingTemplate
from apps.production.scheduling import WorkCenter


def _next_monday(d):
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APSFiniteCapacityScheduleTest(TestCase):
    def setUp(self):
        # 两个日产能均为 8 小时、效率 100% 的工作中心
        self.wc1 = WorkCenter.objects.create(
            code='WC-1', name='机加中心', capacity_per_day=Decimal('8'), efficiency=Decimal('100')
        )
        self.wc2 = WorkCenter.objects.create(
            code='WC-2', name='装配中心', capacity_per_day=Decimal('8'), efficiency=Decimal('100')
        )
        self.start = _next_monday(date(2026, 7, 6))

    # ------------------------------------------------------------------ helpers
    def _item_with_routing(self, sku, ops):
        """ops: [(operation_name, work_center, setup_hours, standard_hours, cycle_time_sec)]"""
        item = Item.objects.create(sku=sku, name=f'物料-{sku}')
        tpl = RoutingTemplate.objects.create(
            code=f'RT-{sku}', name=f'工艺-{sku}', item=item, is_active=True, is_current=True
        )
        for i, (name, wc, setup, std, cyc) in enumerate(ops, start=1):
            RoutingOperation.objects.create(
                routing=tpl,
                sequence=i,
                operation_code=f'OP{i}',
                operation_name=name,
                work_center=wc,
                setup_hours=Decimal(str(setup)),
                standard_hours=Decimal(str(std)),
                cycle_time=Decimal(str(cyc)),
            )
        return item

    def _order(self, order_no, item, qty, required_date, priority=3):
        return ScheduleOrder.objects.create(
            order_no=order_no,
            item=item,
            quantity=Decimal(str(qty)),
            required_date=required_date,
            priority=priority,
            status='PENDING',
        )

    # -------------------------------------------------------------------- tests
    def test_hours_derived_from_routing_standard_hours(self):
        """两道工序的工单：工时 = Σ(setup + 数量×standard_hours)，而非 quantity×1。"""
        item = self._item_with_routing(
            'TWO-OP',
            [
                ('粗加工', self.wc1, 1, 2, 0),      # 1 + 3×2 = 7h @ WC1
                ('精装配', self.wc2, 0.5, 1.5, 0),  # 0.5 + 3×1.5 = 5h @ WC2
            ],
        )
        order = self._order('SCH-DERIVE', item, qty=3, required_date=self.start)

        APSService.auto_schedule(
            orders=[order], start_date=self.start, return_stats=True, create_tasks=True
        )
        order.refresh_from_db()

        # 12h 来自工艺路线；quantity×1 只会得到 3
        self.assertEqual(order.planned_hours, Decimal('12.00'))
        self.assertNotEqual(order.planned_hours, order.quantity)
        self.assertEqual(order.status, 'SCHEDULED')

        tasks = list(APSScheduleTask.objects.filter(order=order, is_deleted=False).order_by('sequence'))
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].work_center_id, self.wc1.id)
        self.assertEqual(tasks[0].planned_hours, Decimal('7.00'))
        self.assertEqual(tasks[1].work_center_id, self.wc2.id)
        self.assertEqual(tasks[1].planned_hours, Decimal('5.00'))
        # 工序在订单内串行：第二道不早于第一道结束
        self.assertGreaterEqual(tasks[1].planned_start, tasks[0].planned_end)

    def test_cycle_time_used_when_standard_hours_missing(self):
        """standard_hours 缺失时退化为 cycle_time/3600 计算单件工时。"""
        # cycle_time=3600s=1h/件，setup=0，qty=4 -> 4h
        item = self._item_with_routing('CYCLE-OP', [('冲压', self.wc1, 0, 0, 3600)])
        order = self._order('SCH-CYCLE', item, qty=4, required_date=self.start)

        APSService.auto_schedule(orders=[order], start_date=self.start)
        order.refresh_from_db()

        self.assertEqual(order.planned_hours, Decimal('4.00'))

    def test_orders_exceeding_daily_capacity_spill_to_next_working_day(self):
        """同一工作中心上两个各 6h 的工单叠加超过 8h/日 -> 后者顺延到下一个工作日。"""
        item = self._item_with_routing('SPILL-OP', [('加工', self.wc1, 0, 6, 0)])
        order_a = self._order('SCH-A', item, qty=1, required_date=self.start, priority=2)
        order_b = self._order('SCH-B', item, qty=1, required_date=self.start + timedelta(days=1), priority=2)

        APSService.auto_schedule(orders=[order_a, order_b], start_date=self.start)
        order_a.refresh_from_db()
        order_b.refresh_from_db()

        self.assertEqual(order_a.work_center_id, self.wc1.id)
        self.assertEqual(order_b.work_center_id, self.wc1.id)
        # A 在起始工作日；B 因产能不足顺延到之后的工作日
        self.assertEqual(order_a.planned_start.date(), self.start)
        self.assertGreater(order_b.planned_start.date(), order_a.planned_start.date())
        # 顺延目标仍是工作日（非周末）
        self.assertLess(order_b.planned_start.date().weekday(), 5)

    def test_higher_priority_scheduled_before_lower(self):
        """高优先级(数值小)工单先占用产能，即使其需求日期更晚。"""
        item = self._item_with_routing('PRIO-OP', [('加工', self.wc1, 0, 2, 0)])
        low = self._order('SCH-LOW', item, qty=1, required_date=self.start, priority=4)
        high = self._order('SCH-HIGH', item, qty=1, required_date=self.start + timedelta(days=5), priority=1)

        # orders=None -> 服务内部按 (priority, required_date) 排序
        APSService.auto_schedule(start_date=self.start)
        low.refresh_from_db()
        high.refresh_from_db()

        self.assertLess(high.planned_start, low.planned_start)

    def test_earlier_due_date_scheduled_first_when_same_priority(self):
        """同优先级时，需求日期更早的工单先排。"""
        item = self._item_with_routing('DUE-OP', [('加工', self.wc1, 0, 2, 0)])
        later = self._order('SCH-LATER', item, qty=1, required_date=self.start + timedelta(days=10), priority=3)
        earlier = self._order('SCH-EARLIER', item, qty=1, required_date=self.start, priority=3)

        APSService.auto_schedule(start_date=self.start)
        later.refresh_from_db()
        earlier.refresh_from_db()

        self.assertLess(earlier.planned_start, later.planned_start)

    def test_utilization_between_0_and_100(self):
        """各工作中心利用率为真实值且落在 [0, 100]，且至少有一个 > 0。"""
        item = self._item_with_routing('UTIL-OP', [('加工', self.wc1, 0, 6, 0)])
        self._order('SCH-U1', item, qty=1, required_date=self.start, priority=2)
        self._order('SCH-U2', item, qty=1, required_date=self.start, priority=2)

        result = APSService.auto_schedule(start_date=self.start, return_stats=True)

        self.assertGreaterEqual(result['scheduled_count'], 2)
        utils = [wc['utilization'] for wc in result['work_centers']]
        for u in utils:
            self.assertGreaterEqual(u, 0.0)
            self.assertLessEqual(u, 100.0)
        self.assertTrue(any(u > 0 for u in utils))

    def test_fallback_when_no_routing_uses_default(self):
        """无工艺路线时回退：无 planned_hours -> 数量×默认单件工时(1h)。"""
        item = Item.objects.create(sku='NO-RT', name='无工艺物料')
        order = self._order('SCH-FALLBACK', item, qty=5, required_date=self.start)

        APSService.auto_schedule(orders=[order], start_date=self.start)
        order.refresh_from_db()

        self.assertEqual(order.status, 'SCHEDULED')
        self.assertEqual(order.planned_hours, Decimal('5.00'))  # 5 × 1h

    def test_reschedule_is_idempotent_for_tasks(self):
        """重复排程(create_tasks)不产生重复 PENDING 子任务。"""
        item = self._item_with_routing('IDEMP-OP', [('加工', self.wc1, 0, 2, 0)])
        order = self._order('SCH-IDEMP', item, qty=1, required_date=self.start)

        APSService.auto_schedule(orders=[order], start_date=self.start, create_tasks=True)
        APSService.auto_schedule(orders=[order], start_date=self.start, create_tasks=True)

        self.assertEqual(APSScheduleTask.objects.filter(order=order, is_deleted=False).count(), 1)


class FiniteCapacitySchedulerTest(TestCase):
    def _aware(self, y, mo, d, h, mi=0):
        return timezone.make_aware(datetime(y, mo, d, h, mi))

    def test_priority_strategy_orders_by_sequence_and_computes_utilization(self):
        """priority_based 策略按 sequence 排入；同资源无重叠；avg_utilization 真实计算。"""
        plan = FiniteCapacityPlan.objects.create(
            name='P1',
            plan_start=date(2026, 7, 6),
            plan_end=date(2026, 7, 10),
            scheduling_strategy='priority_based',
            consider_setup_time=False,
        )
        t0 = self._aware(2026, 7, 6, 8)
        ScheduledTask.objects.create(
            plan=plan, work_order='WO-2', resource='R1', start_time=t0,
            end_time=t0 + timedelta(minutes=60), processing_time_minutes=60, sequence=2,
        )
        ScheduledTask.objects.create(
            plan=plan, work_order='WO-1', resource='R1', start_time=t0,
            end_time=t0 + timedelta(minutes=120), processing_time_minutes=120, sequence=1,
        )

        FiniteCapacityScheduler.run_schedule(plan.id)
        plan.refresh_from_db()

        self.assertEqual(plan.status, 'completed')
        self.assertEqual(plan.total_tasks, 2)

        wo1 = ScheduledTask.objects.get(plan=plan, work_order='WO-1')
        wo2 = ScheduledTask.objects.get(plan=plan, work_order='WO-2')
        # sequence 小(WO-1)先排：t0..+120，随后 WO-2：+120..+180（无重叠）
        self.assertEqual(wo1.start_time, t0)
        self.assertEqual(wo2.start_time, t0 + timedelta(minutes=120))
        self.assertGreaterEqual(wo2.start_time, wo1.end_time)

        # 单资源、无空隙 -> 利用率 100%，落在 [0,100]
        self.assertGreaterEqual(plan.avg_utilization, Decimal('0'))
        self.assertLessEqual(plan.avg_utilization, Decimal('100'))
        self.assertEqual(plan.avg_utilization, Decimal('100.00'))

    def test_earliest_start_strategy_sequences_by_requested_start(self):
        """earliest_start 策略：请求开始时间早者先排（体现策略生效）。"""
        plan = FiniteCapacityPlan.objects.create(
            name='P2',
            plan_start=date(2026, 7, 6),
            plan_end=date(2026, 7, 10),
            scheduling_strategy='earliest_start',
            consider_setup_time=False,
        )
        early = self._aware(2026, 7, 6, 8)
        late = self._aware(2026, 7, 6, 10)
        # 故意让"晚开始"的任务 sequence 更小，验证排序依据是 start_time 而非 sequence
        ScheduledTask.objects.create(
            plan=plan, work_order='WO-LATE', resource='R1', start_time=late,
            end_time=late + timedelta(minutes=60), processing_time_minutes=60, sequence=1,
        )
        ScheduledTask.objects.create(
            plan=plan, work_order='WO-EARLY', resource='R1', start_time=early,
            end_time=early + timedelta(minutes=60), processing_time_minutes=60, sequence=2,
        )

        FiniteCapacityScheduler.run_schedule(plan.id)

        wo_early = ScheduledTask.objects.get(plan=plan, work_order='WO-EARLY')
        wo_late = ScheduledTask.objects.get(plan=plan, work_order='WO-LATE')
        # 早开始的先占资源，晚开始的被顺延到其后
        self.assertEqual(wo_early.start_time, early)
        self.assertGreaterEqual(wo_late.start_time, wo_early.end_time)
