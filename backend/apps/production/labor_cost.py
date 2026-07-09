"""
报工 -> 人工成本 服务

打通「主报工动作只回写工时、不产生成本」的断链：
在报工写入 ProductionLog / 回写工序实际工时后，按 `工时 × 工种标准费率`
生成一条 ProjectCostDetail（成本要素=直接人工 DIRECT_LABOR）成本明细，
挂到项目上并回溯到报工单。

设计要点：
- 幂等：以报工单（ProductionLog / ProductionPlanProcess）为稳定来源引用
  （source_type=TIMESHEET + source_doc_type=模型名 + source_doc_id=主键），
  同一报工只会产生一条人工成本明细，重复调用为无操作。
- 事务保护（savepoint）：成本写入失败绝不影响报工主流程。
- 无项目 -> 直接无操作。
"""

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# ProductionProcess.process_type -> LaborRateStandard.work_type
# 生产工序类型与人工费率标准工作类型的映射（找不到对应时回退到默认工种）
PROCESS_TYPE_TO_WORK_TYPE = {
    'MACHINING': 'ASSEMBLY_MECHANICAL',   # 机加工 -> 机械装配
    'WELDING': 'ASSEMBLY_MECHANICAL',     # 焊接   -> 机械装配
    'ASSEMBLY': 'ASSEMBLY_MECHANICAL',    # 装配   -> 机械装配
    'WIRING': 'ASSEMBLY_ELECTRICAL',      # 布线   -> 电气安装
    'PROGRAMMING': 'DEBUGGING',           # 编程调试 -> 调试
    'TESTING': 'QUALITY_CHECK',           # 测试   -> 质量检验
    'PAINTING': 'ASSEMBLY_MECHANICAL',    # 喷涂   -> 机械装配
    'PACKAGING': 'ASSEMBLY_MECHANICAL',   # 包装   -> 机械装配
    'OTHER': 'ASSEMBLY_MECHANICAL',       # 其他   -> 机械装配
}

# 无法从工序解析工种时使用的默认工种
DEFAULT_WORK_TYPE = 'ASSEMBLY_MECHANICAL'


def resolve_work_type(process_type):
    """将生产工序类型解析为人工费率标准的工种；未知/为空回退到默认工种。"""
    if not process_type:
        return DEFAULT_WORK_TYPE
    return PROCESS_TYPE_TO_WORK_TYPE.get(process_type, DEFAULT_WORK_TYPE)


def _to_decimal(value):
    """安全转换为 Decimal，异常返回 0。"""
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _default_labor_rate():
    """默认人工费率（未配置对应工种费率标准时使用），可经 settings 覆盖。"""
    return _to_decimal(getattr(settings, 'PRODUCTION_DEFAULT_LABOR_RATE', Decimal('0')))


def _resolve_rate(work_type):
    """按工种查人工费率标准（work_type 唯一，至多一条）；无则用默认费率。"""
    from apps.projects.advanced_cost_tracking import LaborRateStandard

    if work_type:
        rate_std = LaborRateStandard.objects.filter(work_type=work_type).first()
        if rate_std is not None:
            return rate_std.standard_rate, rate_std
    return _default_labor_rate(), None


def _resolve_process(report_or_planprocess):
    """从报工单/计划工序解析所属工序（用于描述和工种回退），失败返回 None。"""
    try:
        # ProductionLog: -> plan_process -> process
        plan_process = getattr(report_or_planprocess, 'plan_process', None)
        if plan_process is not None:
            return getattr(plan_process, 'process', None)
        # ProductionPlanProcess: -> process
        return getattr(report_or_planprocess, 'process', None)
    except Exception:  # pragma: no cover - 纯防御
        return None


def _resolve_doc_no(report_or_planprocess):
    """解析报工单对应的计划编号（source_doc_no），失败返回空串。"""
    try:
        plan_process = getattr(report_or_planprocess, 'plan_process', None)
        if plan_process is None:
            plan_process = report_or_planprocess
        plan = getattr(plan_process, 'plan', None)
        return getattr(plan, 'plan_no', '') or ''
    except Exception:  # pragma: no cover - 纯防御
        return ''


def post_labor_cost(report_or_planprocess, work_hours, work_type, user, project):
    """
    为一次报工生成人工成本明细（ProjectCostDetail，DIRECT_LABOR）。

    参数：
        report_or_planprocess: ProductionLog（首选，报工单）或 ProductionPlanProcess。
                               作为幂等键的稳定来源引用。
        work_hours: 本次报工工时（Decimal/数值）。
        work_type:  人工费率标准工种（LaborRateStandard.work_type），
                    可为 None（回退默认费率）。
        user:       操作人（写入 created_by / responsible_user）。
        project:    所属项目（projects.Project）。为空则无操作。

    返回：创建/已存在的 ProjectCostDetail；无项目或失败时返回 None。
    幂等：同一 report_or_planprocess 只产生一条明细，重复调用返回既有明细。
    """
    if project is None:
        return None

    try:
        with transaction.atomic():
            from apps.projects.advanced_cost_tracking import ProjectCostDetail

            source_doc_type = type(report_or_planprocess).__name__
            source_doc_id = getattr(report_or_planprocess, 'pk', None)
            if source_doc_id is None:
                return None

            hours = _to_decimal(work_hours)
            rate, _rate_std = _resolve_rate(work_type)
            amount = (hours * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            process = _resolve_process(report_or_planprocess)
            process_name = getattr(process, 'name', '') if process is not None else ''
            work_type_display = ''
            try:
                from apps.projects.advanced_cost_tracking import LaborRateStandard

                choices = dict(LaborRateStandard._meta.get_field('work_type').choices)
                work_type_display = choices.get(work_type, work_type or '')
            except Exception:  # pragma: no cover - 纯防御
                work_type_display = work_type or ''

            cost_date = getattr(report_or_planprocess, 'log_date', None) or timezone.now().date()
            doc_no = _resolve_doc_no(report_or_planprocess)

            desc = f'生产报工人工成本 - {process_name or "工序"}'
            if work_type_display:
                desc = f'{desc}（{work_type_display}）'

            # 幂等键：TIMESHEET 来源 + 报工单模型名 + 报工单主键 + 直接人工
            cost_detail, _created = ProjectCostDetail.objects.get_or_create(
                project=project,
                source_type='TIMESHEET',
                source_doc_type=source_doc_type,
                source_doc_id=source_doc_id,
                cost_element='DIRECT_LABOR',
                defaults={
                    'source_doc_no': doc_no,
                    'cost_date': cost_date,
                    'project_phase': 'PRODUCTION',
                    'description': desc[:500],
                    'quantity': hours,
                    'unit': '小时',
                    'unit_cost': rate,
                    'actual_amount': amount,
                    'standard_amount': amount,
                    'responsible_user': user,
                    'created_by': user,
                    'updated_by': user,
                },
            )
            return cost_detail
    except Exception:
        # 成本登记失败绝不阻断报工主流程
        logger.exception(
            '报工人工成本登记失败 (source=%s#%s, project=%s)',
            type(report_or_planprocess).__name__,
            getattr(report_or_planprocess, 'pk', None),
            getattr(project, 'pk', None),
        )
        return None
