"""
项目工序排程
Project Operation Scheduling

功能：基于项目的生产任务排程

非标自动化行业适用说明：
- 每个排程工单对应项目的一个生产任务
- 数量(quantity)字段通常为1（单件生产）
- 重点是工序时间和资源分配，而非数量完成率
- 优先级基于项目交付日期

注：此模块已简化，适合项目型单件/小批量生产排程
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# 从scheduling导入WorkCenter，避免重复定义
from .scheduling import WorkCenter


class ScheduleOrder(BaseModel):
    """排程工单"""

    STATUS_CHOICES = [
        ('PENDING', '待排程'),
        ('SCHEDULED', '已排程'),
        ('IN_PROGRESS', '生产中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    PRIORITY_CHOICES = [
        (1, '最高'),
        (2, '高'),
        (3, '中'),
        (4, '低'),
        (5, '最低'),
    ]

    order_no = models.CharField(max_length=50, unique=True, verbose_name='工单编号')

    # 来源
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='来源项目',
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='来源订单',
    )

    # 产品
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='产品',
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4, verbose_name='数量')

    # 时间要求
    required_date = models.DateField(verbose_name='需求日期')
    earliest_start = models.DateField(null=True, blank=True, verbose_name='最早开始')

    # 排程结果
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='工作中心',
    )
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name='计划结束')
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='计划工时')

    # 实际
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')
    completed_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='完成数量')

    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3, verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'mes_schedule_order'
        verbose_name = '排程工单'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'required_date']

    def __str__(self):
        return self.order_no

    def save(self, *args, **kwargs):
        if not self.order_no:
            from apps.core.utils import generate_code

            self.order_no = generate_code('SCH')
        super().save(*args, **kwargs)


class APSScheduleTask(BaseModel):
    """APS排程任务"""

    STATUS_CHOICES = [
        ('PENDING', '待开始'),
        ('IN_PROGRESS', '进行中'),
        ('PAUSED', '暂停'),
        ('COMPLETED', '已完成'),
    ]

    order = models.ForeignKey(ScheduleOrder, on_delete=models.CASCADE, related_name='tasks', verbose_name='工单')

    sequence = models.IntegerField(default=1, verbose_name='工序序号')
    process_name = models.CharField(max_length=100, verbose_name='工序名称')

    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aps_schedule_tasks',
        verbose_name='工作中心',
    )

    # 时间
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name='计划结束')
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='计划工时')

    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')
    actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='实际工时')

    # 操作人
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aps_schedule_tasks',
        verbose_name='操作人',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    progress = models.IntegerField(default=0, verbose_name='进度(%)')

    class Meta:
        app_label = 'production'
        db_table = 'mes_aps_schedule_task'
        verbose_name = 'APS排程任务'
        verbose_name_plural = verbose_name
        ordering = ['order', 'sequence']


# ---------------------------------------------------------------------------
# 有限产能排程辅助（工作日历 + 工作中心日产能）
#
# 算法概述（启发式，非 OR 最优解）：
#   - 每个工单的工时来自其工艺路线的各道工序，而非旧的 quantity×1。
#     单件工时取工序 standard_hours，缺失时退化为 cycle_time/3600；
#     工序工时 = setup_hours + 数量 × 单件工时。
#   - 每道工序被前向排入其工序指定的工作中心，遵守该中心的有限日产能
#     (capacity_per_day × efficiency) 与工作日历（默认跳过周末）。
#   - 工单按优先级(数值小=优先) + 需求日期(早者先) 排序后依次占用产能，
#     形成"先到先占"的有限产能日历；据此计算真实的各中心利用率。
# ---------------------------------------------------------------------------

# 工作班次名义开始时刻（把"日产能小时"落到具体的开始/结束时刻）
WORK_DAY_START_HOUR = 8
# 无工艺路线且无 planned_hours 时的兜底单件工时（保持与旧口径 quantity×1 一致）
DEFAULT_HOURS_PER_UNIT = 1.0


def _next_working_day(d):
    """返回 d 当天或其后的第一个工作日（默认跳过周六/周日）。"""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _count_working_days(start, end):
    """[start, end] 闭区间内的工作日数量（含端点，跳过周末）。"""
    if end < start:
        return 0
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


def _effective_daily_hours(wc):
    """工作中心有效日产能小时 = capacity_per_day × efficiency%。"""
    cap = float(wc.capacity_per_day or 0)
    eff = float(wc.efficiency if wc.efficiency is not None else 100) / 100.0
    val = cap * eff
    return val if val > 0 else 0.0


def _work_day_start(d):
    """某工作日的名义班次开始时刻（时区感知，与 USE_TZ=True 对齐）。"""
    naive = datetime.combine(d, time(WORK_DAY_START_HOUR))
    if timezone.is_naive(naive):
        return timezone.make_aware(naive)
    return naive


def _allocate_operation(wc_id, run_hours, earliest_dt, cap_hours, day_used, horizon_guard=3660):
    """把一道工序（run_hours 小时）前向排入工作中心 wc_id 的有限产能日历。

    规则：
    - 不早于 earliest_dt；跳过周末；遵守该中心每个工作日的有限产能 cap_hours。
    - 工序若能在单个工作日的剩余产能内完成，则整段放入第一个有足够剩余产能的
      工作日（不做跨夜拆分）——两个工单叠加超过日产能时，后者自然顺延到下一个
      工作日；超过整日产能的大工序按工作日贪心填充、跨多个工作日。
    - 就地累加 day_used[(wc_id, date)]，返回 (start_dt, end_dt)。
    """
    eps = 1e-6
    if cap_hours <= 0:
        # 退化：工作中心未配置产能，按连续时间直接排（不阻塞整体排程）
        return earliest_dt, earliest_dt + timedelta(hours=run_hours)

    day = _next_working_day(earliest_dt.date())

    if run_hours <= cap_hours + eps:
        guard = 0
        while guard < horizon_guard:
            guard += 1
            day = _next_working_day(day)
            used = day_used.get((wc_id, day), 0.0)
            candidate = _work_day_start(day) + timedelta(hours=used)
            if day == earliest_dt.date() and candidate < earliest_dt:
                candidate = earliest_dt
                used = (candidate - _work_day_start(day)).total_seconds() / 3600.0
            if cap_hours - used >= run_hours - eps:
                end = candidate + timedelta(hours=run_hours)
                day_used[(wc_id, day)] = used + run_hours
                return candidate, end
            day = day + timedelta(days=1)
        return earliest_dt, earliest_dt + timedelta(hours=run_hours)

    # 大工序：跨工作日贪心填充
    remaining = run_hours
    op_start = None
    seg_end = None
    guard = 0
    while remaining > eps and guard < horizon_guard:
        guard += 1
        day = _next_working_day(day)
        used = day_used.get((wc_id, day), 0.0)
        candidate = _work_day_start(day) + timedelta(hours=used)
        if op_start is None and day == earliest_dt.date() and candidate < earliest_dt:
            candidate = earliest_dt
            used = (candidate - _work_day_start(day)).total_seconds() / 3600.0
        free = cap_hours - used
        if free <= eps:
            day = day + timedelta(days=1)
            continue
        if op_start is None:
            op_start = candidate
        take = min(remaining, free)
        seg_end = candidate + timedelta(hours=take)
        day_used[(wc_id, day)] = used + take
        remaining -= take
        day = day + timedelta(days=1)
    if op_start is None:
        op_start = earliest_dt
        seg_end = earliest_dt + timedelta(hours=run_hours)
    return op_start, seg_end


class APSService:
    """APS排程服务"""

    @staticmethod
    def auto_schedule(orders=None, start_date=None, return_stats=False, create_tasks=False):
        """有限产能自动排产。

        从工艺路线推导每个工单的工序与工时（item RoutingTemplate 优先，其次
        project ProjectRouting），把每道工序前向排入其工序指定的工作中心，遵守该
        中心的有限日产能 (capacity_per_day × efficiency) 与工作日历（默认跳过周末），
        按优先级(数值小=优先) + 需求日期(早者先) 排序占用产能。无工艺路线时回退到
        planned_hours 或 数量 × 默认单件工时。

        参数：
        - orders：待排工单，默认取全部 PENDING。
        - start_date：排程起始日期，默认今天。
        - return_stats：True 时返回 dict（含真实各中心利用率）；False（默认）返回
          已排产工单数(int)，与旧签名向后兼容。
        - create_tasks：True 时按工序落地/刷新 APSScheduleTask（幂等：仅重建 PENDING
          任务，保留已开始/完成的任务）。默认 False，保持旧行为不写子任务。
        """
        if start_date is None:
            start_date = date.today()

        if orders is None:
            orders = ScheduleOrder.objects.filter(status='PENDING', is_deleted=False)

        # 排序：优先级升序(1=最高) + 需求日期升序(早者先)
        orders = sorted(orders, key=lambda o: (o.priority or 3, o.required_date or date.max))

        work_centers = list(WorkCenter.objects.filter(is_active=True, is_deleted=False))
        cap_by_wc = {wc.id: _effective_daily_hours(wc) for wc in work_centers}

        # 有限产能日历：{(work_center_id, date): 已占用小时}
        day_used = {}
        scheduled_count = 0

        for order in orders:
            specs = APSService._derive_operations(order)
            if not specs:
                # 回退：无工艺路线 -> 单一伪工序，工时取 planned_hours 或 数量×默认单件工时
                if order.planned_hours:
                    fb_hours = float(order.planned_hours)
                else:
                    fb_hours = float(order.quantity or 0) * DEFAULT_HOURS_PER_UNIT
                if fb_hours <= 0:
                    fb_hours = DEFAULT_HOURS_PER_UNIT
                specs = [
                    {
                        'sequence': 1,
                        'name': order.item.name if order.item else order.order_no,
                        'work_center': None,
                        'hours': fb_hours,
                        'setup': 0.0,
                    }
                ]

            # 该工单的最早可开工时间（不早于 start_date）
            base_date = order.earliest_start or start_date
            if base_date < start_date:
                base_date = start_date
            op_cursor = _work_day_start(_next_working_day(base_date))

            first_start = None
            last_end = None
            primary_wc = None
            task_rows = []

            for spec in specs:
                wc = spec['work_center']
                if wc is None or wc.id not in cap_by_wc:
                    wc = APSService._pick_fallback_wc(work_centers, day_used)
                if wc is None:
                    # 无任何可用工作中心，放弃该工单（保持 PENDING）
                    break

                cap_h = cap_by_wc.get(wc.id, _effective_daily_hours(wc))
                run_h = spec['hours'] if spec['hours'] and spec['hours'] > 0 else (spec['setup'] or 0.0)
                if run_h <= 0:
                    run_h = DEFAULT_HOURS_PER_UNIT

                s_dt, e_dt = _allocate_operation(wc.id, run_h, op_cursor, cap_h, day_used)

                if first_start is None:
                    first_start = s_dt
                    primary_wc = wc
                last_end = e_dt
                op_cursor = e_dt  # 工序在订单内串行：下一道不早于本道结束

                task_rows.append(
                    {
                        'sequence': spec['sequence'],
                        'name': spec['name'],
                        'wc': wc,
                        'start': s_dt,
                        'end': e_dt,
                        'hours': run_h,
                    }
                )

            if first_start is None:
                continue  # 未能排入任何工序（无工作中心）

            total_hours = sum(row['hours'] for row in task_rows)
            order.work_center = primary_wc
            order.planned_start = first_start
            order.planned_end = last_end
            order.planned_hours = Decimal(str(round(total_hours, 2)))
            order.status = 'SCHEDULED'
            order.save()

            if create_tasks:
                APSService._regenerate_tasks(order, task_rows)

            scheduled_count += 1

        if not return_stats:
            return scheduled_count

        utilization = APSService._compute_utilization(work_centers, cap_by_wc, day_used, start_date)
        return {
            'scheduled_count': scheduled_count,
            'utilization': {wc_id: round(pct, 1) for wc_id, pct in utilization.items()},
            'work_centers': [
                {
                    'work_center_id': wc.id,
                    'work_center_name': wc.name,
                    'utilization': round(utilization.get(wc.id, 0.0), 1),
                }
                for wc in work_centers
            ],
        }

    @staticmethod
    def _derive_operations(order):
        """从工艺路线推导工单的工序序列。

        返回 [{'sequence', 'name', 'work_center'(obj|None), 'hours'(float), 'setup'(float)}]；
        无工艺路线时返回 []（由调用方走兜底）。

        来源优先级：
        1) 物料工艺模板 RoutingTemplate（含 work_center / setup_hours / standard_hours /
           cycle_time，最贴合本需求）：工时 = setup + 数量 × 单件工时；
           单件工时取 standard_hours，缺失时用 cycle_time/3600。
        2) 项目工艺路线 ProjectRouting（工序 work_center 取自 work_station.work_center，
           工时取 planned_hours 或 standard_hours 作为该工序总工时）。
        """
        from .routing import ProjectRouting, RoutingTemplate

        qty = float(order.quantity or 0)
        if qty <= 0:
            qty = 1.0

        # 1) 物料工艺模板
        if order.item_id:
            template = (
                RoutingTemplate.objects.filter(item_id=order.item_id, is_active=True, is_deleted=False)
                .order_by('-is_current', '-created_at')
                .first()
            )
            if template:
                specs = []
                for op in template.operations.filter(is_deleted=False).order_by('sequence'):
                    setup = float(op.setup_hours or 0)
                    per_piece = float(op.standard_hours or 0)
                    if per_piece <= 0 and float(op.cycle_time or 0) > 0:
                        per_piece = float(op.cycle_time) / 3600.0
                    specs.append(
                        {
                            'sequence': op.sequence,
                            'name': op.operation_name,
                            'work_center': op.work_center,
                            'hours': setup + qty * per_piece,
                            'setup': setup,
                        }
                    )
                if specs:
                    return specs

        # 2) 项目工艺路线
        if order.project_id:
            routing = (
                ProjectRouting.objects.filter(project_id=order.project_id, is_deleted=False)
                .order_by('-created_at')
                .first()
            )
            if routing:
                specs = []
                for op in routing.operations.filter(is_deleted=False).order_by('sequence'):
                    base = float(op.planned_hours or 0) or float(op.standard_hours or 0)
                    wc = op.work_station.work_center if op.work_station_id else None
                    specs.append(
                        {
                            'sequence': op.sequence,
                            'name': op.operation_name,
                            'work_center': wc,
                            'hours': base,
                            'setup': 0.0,
                        }
                    )
                if specs:
                    return specs

        return []

    @staticmethod
    def _pick_fallback_wc(work_centers, day_used):
        """工序未指定工作中心时的兜底选择：取当前累计占用最少（最空闲）的中心。"""
        if not work_centers:
            return None

        def load(wc):
            return sum(h for (wid, _d), h in day_used.items() if wid == wc.id)

        return min(work_centers, key=lambda wc: (load(wc), wc.id))

    @staticmethod
    def _compute_utilization(work_centers, cap_by_wc, day_used, start_date):
        """计算各工作中心真实利用率(%) = 已占用工时 / (有效日产能 × 排程窗口内工作日数)。

        窗口取 [start_date, 该中心最后一个被占用的工作日]；结果被夹在 [0, 100]。
        """
        result = {}
        for wc in work_centers:
            cap_h = cap_by_wc.get(wc.id, 0.0)
            busy = 0.0
            last_date = None
            for (wid, d), h in day_used.items():
                if wid != wc.id:
                    continue
                busy += h
                if last_date is None or d > last_date:
                    last_date = d
            if cap_h <= 0 or last_date is None:
                result[wc.id] = 0.0
                continue
            working_days = _count_working_days(start_date, last_date)
            available = cap_h * working_days
            pct = (busy / available * 100.0) if available > 0 else 0.0
            result[wc.id] = max(0.0, min(100.0, pct))
        return result

    @staticmethod
    def _regenerate_tasks(order, task_rows):
        """按工序幂等落地 APSScheduleTask：仅重建 PENDING 任务，保留已开始/完成的任务。"""
        APSScheduleTask.objects.filter(order=order, status='PENDING', is_deleted=False).delete()
        for row in task_rows:
            APSScheduleTask.objects.create(
                order=order,
                sequence=row['sequence'],
                process_name=row['name'],
                work_center=row['wc'],
                planned_start=row['start'],
                planned_end=row['end'],
                planned_hours=Decimal(str(round(row['hours'], 2))),
                status='PENDING',
            )

    @staticmethod
    def get_gantt_data(start_date=None, end_date=None):
        """获取甘特图数据"""
        qs = ScheduleOrder.objects.filter(status__in=['SCHEDULED', 'IN_PROGRESS'], is_deleted=False)

        if start_date:
            qs = qs.filter(planned_start__date__gte=start_date)
        if end_date:
            qs = qs.filter(planned_end__date__lte=end_date)

        gantt_data = []
        for order in qs.select_related('work_center', 'item'):
            gantt_data.append(
                {
                    'id': order.id,
                    'order_no': order.order_no,
                    'name': order.item.name if order.item else order.order_no,
                    'work_center': order.work_center.name if order.work_center else '',
                    'start': order.planned_start.isoformat() if order.planned_start else None,
                    'end': order.planned_end.isoformat() if order.planned_end else None,
                    'progress': int(order.completed_qty / order.quantity * 100) if order.quantity else 0,
                    'status': order.status,
                    'priority': order.priority,
                }
            )

        return gantt_data

    @staticmethod
    def get_capacity_view(work_center_id=None, start_date=None, days=7):
        """获取产能视图"""
        if start_date is None:
            start_date = date.today()

        work_centers = WorkCenter.objects.filter(is_active=True, is_deleted=False)
        if work_center_id:
            work_centers = work_centers.filter(id=work_center_id)

        result = []

        for wc in work_centers:
            daily_capacity = float(wc.capacity_per_day)
            wc_data = {
                'work_center_id': wc.id,
                'work_center_name': wc.name,
                'daily_capacity': daily_capacity,
                'days': [],
            }

            for i in range(days):
                check_date = start_date + timedelta(days=i)

                # 获取当天已排程工时
                scheduled_hours = ScheduleOrder.objects.filter(
                    work_center=wc,
                    planned_start__date=check_date,
                    status__in=['SCHEDULED', 'IN_PROGRESS'],
                    is_deleted=False,
                ).aggregate(total=Sum('planned_hours'))['total'] or Decimal('0')

                scheduled = float(scheduled_hours)
                available = max(0, daily_capacity - scheduled)
                utilization = min(100, scheduled / daily_capacity * 100) if daily_capacity > 0 else 0

                wc_data['days'].append(
                    {
                        'date': check_date.isoformat(),
                        'scheduled': scheduled,
                        'available': available,
                        'utilization': round(utilization, 1),
                    }
                )

            result.append(wc_data)

        return result


def post_completion_stock_moves(order, completed_qty, materials, user):
    """完工入库与领料出库对库存的联动。

    在调用方的同一事务内执行：
    - 完工入库：order.item × completed_qty 入到目标仓库（request.warehouse_id 优先，
      否则取 item.default_warehouse），生成 IN 库存移动。
    - 领料出库：materials 为前端显式传入的领料明细
      [{item_id, qty, warehouse_id?}]，逐条生成 OUT_PROJECT 出库移动。

    设计取舍：ScheduleOrder 无工艺路线/BOM 直连，为避免按项目 BOM 整单重复发料导致账实
    损坏，领料明细由调用方显式提供；未提供则只做完工入库。不修改 inventory 代码，仅调用
    其既有 StockMove 公共接口（save() 在 status=COMPLETED 时原子更新库存余额）。
    """
    # 延迟导入避免与 inventory 形成模块级循环依赖
    from apps.inventory.models import StockMove

    moves = []
    today = timezone.now().date()

    # 完工入库
    if order.item and completed_qty and completed_qty > 0:
        target_warehouse = order.item.default_warehouse
        if target_warehouse is None:
            raise serializers.ValidationError(
                {'warehouse': '产品未配置默认仓库，无法生成完工入库，请先为物料设置默认仓库'}
            )
        moves.append(
            StockMove(
                item=order.item,
                warehouse_to=target_warehouse,
                qty=completed_qty,
                unit_cost=Decimal('0'),
                # inventory 现有 move_type 无 IN_PRODUCTION；ADJUSTMENT + warehouse_to
                # 在 inventory 侧路由为入库且方向由仓库字段决定，用 reference 区分来源
                move_type='ADJUSTMENT',
                reference_type='ScheduleOrder',
                reference_id=order.id,
                project=order.project,
                move_date=today,
                status='COMPLETED',
                notes=f'生产完工入库 {order.order_no}',
                created_by=user,
            )
        )

    # 领料出库
    for line in materials or []:
        item_id = line.get('item_id')
        qty_raw = line.get('qty')
        if not item_id or qty_raw in (None, ''):
            continue
        try:
            qty = Decimal(str(qty_raw))
        except (InvalidOperation, TypeError, ValueError):
            raise serializers.ValidationError({'materials': f'领料数量非法: {qty_raw}'})
        if qty <= 0:
            raise serializers.ValidationError({'materials': '领料数量必须大于0'})

        from apps.masterdata.models import Item

        try:
            mat_item = Item.objects.get(pk=item_id, is_deleted=False)
        except Item.DoesNotExist:
            raise serializers.ValidationError({'materials': f'领料物料不存在: {item_id}'})

        src_warehouse = mat_item.default_warehouse
        wh_id = line.get('warehouse_id')
        if wh_id:
            from apps.masterdata.models import Warehouse

            try:
                src_warehouse = Warehouse.objects.get(pk=wh_id, is_deleted=False)
            except Warehouse.DoesNotExist:
                raise serializers.ValidationError({'materials': f'领料仓库不存在: {wh_id}'})
        if src_warehouse is None:
            raise serializers.ValidationError(
                {'materials': f'物料 {mat_item} 未指定领料仓库且无默认仓库'}
            )

        moves.append(
            StockMove(
                item=mat_item,
                warehouse_from=src_warehouse,
                qty=qty,
                unit_cost=Decimal('0'),
                move_type='OUT_PROJECT',
                reference_type='ScheduleOrder',
                reference_id=order.id,
                project=order.project,
                move_date=today,
                status='COMPLETED',
                notes=f'生产领料 {order.order_no}',
                created_by=user,
            )
        )

    # 逐条保存（StockMove.save 内含库存原子更新与库存不足校验）
    for mv in moves:
        mv.save()

    return moves


# =====================
# Serializers
# =====================

# 导入scheduling中的WorkCenterSerializer


class APSScheduleTaskSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = APSScheduleTask
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ScheduleOrderSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    tasks = APSScheduleTaskSerializer(many=True, read_only=True)

    class Meta:
        model = ScheduleOrder
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'order_no']


class ScheduleOrderListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = ScheduleOrder
        fields = [
            'id',
            'order_no',
            'item_name',
            'quantity',
            'required_date',
            'work_center_name',
            'planned_start',
            'planned_end',
            'priority',
            'priority_display',
            'status',
            'status_display',
            'completed_qty',
        ]


# =====================
# ViewSets
# =====================

# WorkCenterViewSet已在scheduling.py中定义


class ScheduleOrderViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排程工单管理"""

    permission_module = 'production'
    permission_resource = 'schedule_order'
    queryset = ScheduleOrder.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'priority', 'work_center', 'project']
    search_fields = ['order_no']
    ordering_fields = ['priority', 'required_date', 'planned_start']

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleOrderListSerializer
        return ScheduleOrderSerializer

    @action(detail=False, methods=['post'])
    def auto_schedule(self, request):
        """自动排程"""
        start_date = request.data.get('start_date')
        if start_date:
            start_date = date.fromisoformat(start_date)

        result = APSService.auto_schedule(start_date=start_date, return_stats=True, create_tasks=True)
        return Response({'success': True, **result})

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始生产（仅允许 SCHEDULED→IN_PROGRESS）"""
        with transaction.atomic():
            order = ScheduleOrder.objects.select_for_update().get(pk=self.get_object().pk)
            if order.status != 'SCHEDULED':
                return Response(
                    {'error': '只有已排程的工单可以开始生产'}, status=status.HTTP_400_BAD_REQUEST
                )
            order.status = 'IN_PROGRESS'
            order.actual_start = timezone.now()
            order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成生产（仅允许 IN_PROGRESS→COMPLETED）

        - 校验 completed_qty 为非负数且不超过 order.quantity。
        - 在同一事务内联动库存：完工入库 + 可选领料出库。库存不足/校验失败整体回滚。
        """
        try:
            with transaction.atomic():
                order = ScheduleOrder.objects.select_for_update().get(pk=self.get_object().pk)
                if order.status != 'IN_PROGRESS':
                    return Response(
                        {'error': '只有生产中的工单可以完成'}, status=status.HTTP_400_BAD_REQUEST
                    )

                raw_qty = request.data.get('completed_qty', order.quantity)
                try:
                    completed_qty = Decimal(str(raw_qty))
                except (InvalidOperation, TypeError, ValueError):
                    return Response({'error': '完成数量非法'}, status=status.HTTP_400_BAD_REQUEST)
                if completed_qty < 0:
                    return Response({'error': '完成数量不能为负'}, status=status.HTTP_400_BAD_REQUEST)
                if completed_qty > order.quantity:
                    return Response(
                        {'error': f'完成数量不能超过工单数量 {order.quantity}'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                order.status = 'COMPLETED'
                order.actual_end = timezone.now()
                order.completed_qty = completed_qty
                order.save()

                # 库存联动（完工入库 + 领料出库）
                post_completion_stock_moves(
                    order, completed_qty, request.data.get('materials'), request.user
                )
        except ValueError as e:
            # StockMove 库存不足等抛 ValueError，整笔事务已回滚，返回干净 400
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(order).data)

    @action(detail=False, methods=['get'])
    def gantt(self, request):
        """甘特图数据"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            start_date = date.fromisoformat(start_date)
        if end_date:
            end_date = date.fromisoformat(end_date)

        data = APSService.get_gantt_data(start_date, end_date)
        return Response(data)

    @action(detail=False, methods=['get'])
    def capacity(self, request):
        """产能视图"""
        work_center_id = request.query_params.get('work_center_id')
        start_date = request.query_params.get('start_date')
        days = int(request.query_params.get('days', 7))

        if start_date:
            start_date = date.fromisoformat(start_date)

        data = APSService.get_capacity_view(work_center_id, start_date, days)
        return Response(data)


class APSScheduleTaskViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """APS排程任务管理"""

    permission_module = 'production'
    permission_resource = 'aps_schedule_task'
    queryset = APSScheduleTask.objects.filter(is_deleted=False)
    serializer_class = APSScheduleTaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['order', 'work_center', 'operator', 'status']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始任务（仅允许 PENDING/PAUSED→IN_PROGRESS）"""
        with transaction.atomic():
            task = APSScheduleTask.objects.select_for_update().get(pk=self.get_object().pk)
            if task.status not in ('PENDING', 'PAUSED'):
                return Response(
                    {'error': '只有待开始或暂停的任务可以开始'}, status=status.HTTP_400_BAD_REQUEST
                )
            task.status = 'IN_PROGRESS'
            if task.actual_start is None:
                task.actual_start = timezone.now()
            task.save()
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务（仅允许 IN_PROGRESS→COMPLETED）"""
        with transaction.atomic():
            task = APSScheduleTask.objects.select_for_update().get(pk=self.get_object().pk)
            if task.status != 'IN_PROGRESS':
                return Response(
                    {'error': '只有进行中的任务可以完成'}, status=status.HTTP_400_BAD_REQUEST
                )
            task.status = 'COMPLETED'
            task.actual_end = timezone.now()
            task.progress = 100

            # 计算实际工时
            if task.actual_start:
                delta = timezone.now() - task.actual_start
                task.actual_hours = Decimal(str(delta.total_seconds() / 3600))

            task.save()
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新进度"""
        task = self.get_object()
        progress = request.data.get('progress', 0)
        task.progress = min(100, max(0, int(progress)))
        task.save()
        return Response(self.get_serializer(task).data)
