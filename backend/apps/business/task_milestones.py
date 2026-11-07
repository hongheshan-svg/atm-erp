"""Fixed equipment-project milestones; tasks remain the only execution records."""

PHASES = (
    ('design', '设计阶段'),
    ('purchase', '采购阶段'),
    ('assembly', '组装阶段'),
    ('test', '调试阶段'),
    ('shipping', '发货阶段'),
    ('site', '客户终验收阶段'),
)
NODES = (
    ('design_3d', 'design', '3D画图', '完成设备布局、机构及接口设计，明确图档版本。'),
    ('design_review', 'design', '3D评审', '组织机械、电气、制造评审，记录问题及闭环结论。'),
    ('design_long_lead', 'design', '长交期物料', '提前确认关键件规格、品牌、数量和最晚到料日，提交采购需求。'),
    ('design_standard_bom', 'design', '标准BOM', '核对标准件编码、型号、数量、单元及需求日期，发布采购用清单。'),
    ('design_electrical_bom', 'design', '电气BOM', '完成电气选型、清单及接口核对，明确替代限制。'),
    ('design_documents', 'design', '其它图档', '提交加工图、电气图、气路图及必要技术资料，标明版本。'),
    ('purchase_long_lead', 'purchase', '长交期', '跟进关键长交期件下单、交期确认和到货异常；收货仍在采购/库存登记。'),
    ('purchase_electrical', 'purchase', '电气料', '核对电气BOM、确认交期并跟进电气物料到货。'),
    ('purchase_other', 'purchase', '其它物料', '跟进其余物料下单、到货和缺料处理。'),
    ('assembly_install', 'assembly', '安装', '按有效图纸完成机械装配，检查紧固、润滑、防护及装配质量。'),
    ('assembly_wiring', 'assembly', '接线', '完成电柜及设备接线、气路连接、线号标识和通电前检查。'),
    ('test_io', 'test', '对信号', '核对I/O、传感器、执行器、安全回路及联锁，记录检查结果。'),
    ('test_manual', 'test', '手动调试', '验证单机构动作、限位、报警和异常恢复。'),
    ('test_auto', 'test', '自动调试', '验证自动流程、节拍、精度及连续运行，形成测试记录。'),
    ('shipping_preacceptance', 'shipping', '客户预验收', '按双方确认的技术协议进行厂内预验收，记录遗留问题。'),
    ('shipping_rectification', 'shipping', '整改', '关闭预验收问题，确认包装、资料及现场条件；无需整改可说明后完成。'),
    ('shipping_dispatch', 'shipping', '发货', '根据实际交付批次自动汇总；全部设备登记发货后完成。'),
    ('site_install', 'site', '现场安装接线', '根据各交付批次安装任务自动汇总；全部设备发货且安装任务完成后完成。'),
    ('site_test', 'site', '现场调试', '核对现场条件、节拍及质量，完成联机运行、培训和资料交接。'),
    ('site_acceptance', 'site', '现场验收', '根据实际交付验收自动汇总；全部设备的交付批次验收后完成。'),
)
DEFINITIONS = {
    code: {'kind': kind, 'title': title, 'description': description} for code, kind, title, description in NODES
}
AUTOMATIC = {'shipping_dispatch', 'site_install', 'site_acceptance'}
PRE_SHIPMENT = ('design', 'purchase', 'assembly', 'test', 'shipping')


def stage_label(task):
    return dict(PHASES).get(
        task.kind, '客户终验收阶段' if task.kind in {'install', 'acceptance'} else task.get_kind_display()
    )


def node_label(task):
    return DEFINITIONS.get(task.milestone, {}).get('title') or {
        'install': '批次安装',
        'acceptance': '批次验收',
        'service': '售后任务',
    }.get(task.kind, '自定义任务')
