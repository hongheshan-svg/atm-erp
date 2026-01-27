"""
非标自动化行业全局BOM表统一格式配置
Unified Global BOM Format Configuration for Non-standard Automation Industry

非标自动化设备BOM包含：
- 机械部件（机加件、钣金件、标准件等，可通过CAD导入）
- 电气元件（PLC、HMI、传感器、电机、驱动器、线缆等）
- 气动元件（气缸、电磁阀、气源处理、气管接头等）
- 液压元件（油缸、液压站、阀组等）
- 外购模组（直线模组、机器人、视觉系统等）
- 标准件（螺丝、轴承、导轨、丝杆等）
- 辅材耗材（润滑油、清洁剂、包装材料等）
- 软件服务（编程调试、培训等）

此模块定义统一的BOM字段格式，用于：
1. 项目BOM表格显示（全局）
2. 基础数据物料主数据管理
3. PLM BOM管理
4. CAD机械BOM导入（机械部分来源）
5. 采购询价BOM
6. 生产领料BOM
"""

# =====================================================
# 非标自动化行业物料分类
# =====================================================

# 物料大类（一级分类）
ITEM_CATEGORY_L1 = [
    ('MECHANICAL', '机械类'),       # 机加件、钣金件、焊接件等
    ('ELECTRICAL', '电气类'),       # PLC、传感器、电机、线缆等
    ('PNEUMATIC', '气动类'),        # 气缸、电磁阀、气管等
    ('HYDRAULIC', '液压类'),        # 油缸、液压站等
    ('STANDARD', '标准件'),         # 螺丝、轴承、导轨等
    ('MODULE', '外购模组'),         # 直线模组、机器人等
    ('CONSUMABLE', '耗材辅料'),     # 润滑油、包装材料等
    ('SOFTWARE', '软件服务'),       # 编程、调试、培训
]

# 物料属性（加工/采购方式）
ITEM_PROPERTY = [
    ('SELF_MADE', '自制件'),        # 自己加工
    ('OUTSOURCED', '外协件'),       # 外协加工
    ('PURCHASED', '外购件'),        # 直接采购成品
    ('STANDARD', '标准件'),         # 标准通用件
    ('CONSUMABLE', '易耗品'),       # 消耗品
    ('VIRTUAL', '虚拟件'),          # 仅用于BOM结构
    ('ASSEMBLY', '组件'),           # 装配件
]

# 机械类细分（CAD导入相关）
MECHANICAL_SUBCATEGORY = [
    ('MACHINING', '机加件'),        # 车铣刨磨
    ('SHEETMETAL', '钣金件'),       # 激光切割、折弯
    ('WELDING', '焊接件'),          # 焊接结构件
    ('CASTING', '铸造件'),          # 铸铁、铸铝
    ('FORGING', '锻造件'),          # 锻件
    ('PRINTING', '3D打印件'),       # 快速成型
    ('OTHER_MECH', '其他机械'),
]

# 电气类细分
ELECTRICAL_SUBCATEGORY = [
    ('PLC', 'PLC控制器'),
    ('HMI', '触摸屏/HMI'),
    ('SERVO', '伺服系统'),
    ('STEPPER', '步进系统'),
    ('VFD', '变频器'),
    ('SENSOR', '传感器'),
    ('SWITCH', '开关/按钮'),
    ('RELAY', '继电器/接触器'),
    ('POWER', '电源/变压器'),
    ('CABLE', '线缆/接插件'),
    ('CABINET', '电气柜/箱体'),
    ('OTHER_ELEC', '其他电气'),
]

# 气动类细分
PNEUMATIC_SUBCATEGORY = [
    ('CYLINDER', '气缸'),
    ('VALVE', '电磁阀'),
    ('FRL', '气源处理'),
    ('FITTING', '气管接头'),
    ('ACTUATOR', '气动执行器'),
    ('GRIPPER', '气动夹爪'),
    ('OTHER_PNEU', '其他气动'),
]

# =====================================================
# 非标自动化行业全局BOM核心字段
# =====================================================

# 基础BOM字段（适用于所有物料类型）
BOM_CORE_FIELDS = [
    {
        'field': 'index',
        'label': '序号',
        'width': 60,
        'type': 'readonly',
        'excel_width': 6,
        'description': '行序号，系统自动生成',
    },
    {
        'field': 'item_code',
        'label': '物料编码',
        'width': 120,
        'type': 'required',
        'excel_width': 15,
        'description': '物料唯一编码，对应物料主数据SKU',
        'mapping': ['sku', 'part_number', 'Part Number', 'Part No', '料号', '编码'],
    },
    {
        'field': 'item_category',
        'label': '物料大类',
        'width': 90,
        'type': 'optional',
        'excel_width': 10,
        'description': '物料一级分类：机械/电气/气动/标准件等',
        'options': [c[1] for c in ITEM_CATEGORY_L1],
    },
    {
        'field': 'item_subcategory',
        'label': '物料小类',
        'width': 90,
        'type': 'optional',
        'excel_width': 10,
        'description': '物料二级分类：机加件/PLC/气缸等',
    },
    {
        'field': 'item_property',
        'label': '物料属性',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '加工方式：自制/外协/外购/标准件',
        'options': [p[1] for p in ITEM_PROPERTY],
    },
    {
        'field': 'has_drawing',
        'label': '有图/无图',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '是否有图纸（机械件适用）',
        'options': ['有图', '无图', '待定', '设计中'],
    },
    {
        'field': 'item_name',
        'label': '物料名称',
        'width': 180,
        'type': 'readonly',
        'excel_width': 25,
        'description': '物料名称，来自物料主数据',
        'mapping': ['name', 'description', 'Description', '名称', '描述'],
    },
    {
        'field': 'specification',
        'label': '规格型号',
        'width': 150,
        'type': 'readonly',
        'excel_width': 20,
        'description': '规格型号，来自物料主数据',
        'mapping': ['specification', 'spec', 'model', '规格', '型号', '规格型号'],
    },
    {
        'field': 'brand_manufacturer',
        'label': '品牌/厂家',
        'width': 120,
        'type': 'optional',
        'excel_width': 15,
        'description': '品牌或生产厂家（电气件必填）',
        'mapping': ['brand', 'manufacturer', 'vendor', '品牌', '厂家', '生产厂家'],
    },
    {
        'field': 'unit',
        'label': '单位',
        'width': 60,
        'type': 'readonly',
        'excel_width': 8,
        'description': '计量单位',
        'mapping': ['unit', 'uom', '单位'],
    },
    {
        'field': 'quantity',
        'label': '数量',
        'width': 80,
        'type': 'required',
        'excel_width': 10,
        'description': '需求数量',
        'mapping': ['qty', 'quantity', 'count', '数量', '用量', '计划数量'],
    },
]

# 采购相关字段
BOM_PURCHASE_FIELDS = [
    {
        'field': 'order_status',
        'label': '采购状态',
        'width': 100,
        'type': 'readonly',
        'excel_width': 12,
        'description': '采购订单状态',
    },
    {
        'field': 'ordered_qty',
        'label': '已下单',
        'width': 80,
        'type': 'readonly',
        'excel_width': 10,
        'description': '已下采购订单数量',
    },
    {
        'field': 'supplier_name',
        'label': '供应商',
        'width': 150,
        'type': 'optional',
        'excel_width': 18,
        'description': '供应商名称',
        'mapping': ['supplier', 'vendor', '供应商'],
    },
    {
        'field': 'delivery_date',
        'label': '交期',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '预计交货日期',
    },
    {
        'field': 'lead_time',
        'label': '采购周期',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '采购周期(天)',
    },
]

# 技术参数字段（电气/气动适用）
BOM_TECHNICAL_FIELDS = [
    {
        'field': 'voltage',
        'label': '电压',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '工作电压（电气件适用）',
    },
    {
        'field': 'current',
        'label': '电流',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '额定电流（电气件适用）',
    },
    {
        'field': 'power',
        'label': '功率',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '额定功率（电机适用）',
    },
    {
        'field': 'pressure',
        'label': '气压',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '工作气压（气动件适用）',
    },
    {
        'field': 'stroke',
        'label': '行程',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '行程长度（气缸/模组适用）',
    },
    {
        'field': 'bore_size',
        'label': '缸径',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '气缸缸径',
    },
]

# 库存相关字段
BOM_INVENTORY_FIELDS = [
    {
        'field': 'received_qty',
        'label': '已入库',
        'width': 80,
        'type': 'readonly',
        'excel_width': 10,
        'description': '已入库数量',
    },
    {
        'field': 'issued_qty',
        'label': '已出库',
        'width': 80,
        'type': 'readonly',
        'excel_width': 10,
        'description': '已出库/领用数量',
    },
    {
        'field': 'remaining_qty',
        'label': '剩余需求',
        'width': 80,
        'type': 'readonly',
        'excel_width': 10,
        'description': '剩余需求数量 = 计划数量 - 已入库',
    },
]

# 成本相关字段
BOM_COST_FIELDS = [
    {
        'field': 'estimated_cost',
        'label': '预估单价',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '预估采购单价',
        'mapping': ['cost', 'price', '单价', '成本'],
    },
    {
        'field': 'total_cost',
        'label': '预估成本',
        'width': 100,
        'type': 'readonly',
        'excel_width': 12,
        'description': '预估总成本 = 单价 × 数量',
    },
    {
        'field': 'actual_cost',
        'label': '实际单价',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '实际采购单价',
    },
]

# 需求相关字段
BOM_REQUIREMENT_FIELDS = [
    {
        'field': 'required_date',
        'label': '需求日期',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '物料需求日期',
    },
    {
        'field': 'requester_name',
        'label': '申请人',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '需求申请人',
    },
    {
        'field': 'priority',
        'label': '优先级',
        'width': 80,
        'type': 'optional',
        'excel_width': 8,
        'description': '需求优先级',
        'options': ['低', '普通', '高', '紧急'],
    },
]

# 工艺相关字段（非标自动化专用）
BOM_PROCESS_FIELDS = [
    {
        'field': 'work_center',
        'label': '装配工位',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '装配所在工位',
    },
    {
        'field': 'process_name',
        'label': '工序',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '关联工序',
    },
    {
        'field': 'assembly_sequence',
        'label': '装配顺序',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '装配顺序号',
    },
]

# 图纸相关字段
BOM_DRAWING_FIELDS = [
    {
        'field': 'drawing_no',
        'label': '图纸号',
        'width': 120,
        'type': 'optional',
        'excel_width': 15,
        'description': '关联图纸编号',
    },
    {
        'field': 'drawing_version',
        'label': '图纸版本',
        'width': 80,
        'type': 'optional',
        'excel_width': 10,
        'description': '图纸版本号',
    },
    {
        'field': 'material_spec',
        'label': '材质规格',
        'width': 120,
        'type': 'optional',
        'excel_width': 15,
        'description': '材质要求',
        'mapping': ['material', '材料', '材质'],
    },
    {
        'field': 'surface_treatment',
        'label': '表面处理',
        'width': 100,
        'type': 'optional',
        'excel_width': 12,
        'description': '表面处理要求',
    },
]


# =====================================================
# 预定义的BOM表格配置
# =====================================================

# 项目BOM表格（前端显示）- 完整版（全局BOM）
PROJECT_BOM_TABLE_COLUMNS = (
    BOM_CORE_FIELDS + 
    BOM_PURCHASE_FIELDS + 
    BOM_INVENTORY_FIELDS + 
    BOM_COST_FIELDS[:2] +  # 预估单价、预估成本
    BOM_REQUIREMENT_FIELDS[:2]  # 需求日期、申请人
)

# 项目BOM导入模板 - 通用版（适用于所有物料类型）
PROJECT_BOM_IMPORT_TEMPLATE = [
    f for f in BOM_CORE_FIELDS
] + [
    BOM_REQUIREMENT_FIELDS[0],  # 需求日期
    BOM_REQUIREMENT_FIELDS[1],  # 申请人
]

# 项目BOM导出 - 与导入模板一致
PROJECT_BOM_EXPORT_COLUMNS = PROJECT_BOM_IMPORT_TEMPLATE

# 机械BOM模板（CAD导入专用）- 仅机械部分
MECHANICAL_BOM_TEMPLATE = [
    {'field': 'index', 'label': '序号', 'width': 60, 'type': 'readonly', 'excel_width': 6},
    {'field': 'item_code', 'label': '物料编码', 'width': 120, 'type': 'required', 'excel_width': 15},
    {'field': 'has_drawing', 'label': '有图/无图', 'width': 80, 'type': 'optional', 'excel_width': 10},
    {'field': 'mech_type', 'label': '加工类型', 'width': 90, 'type': 'optional', 'excel_width': 10,
     'options': ['机加件', '钣金件', '焊接件', '铸造件', '3D打印']},
    {'field': 'item_name', 'label': '物料名称', 'width': 180, 'type': 'readonly', 'excel_width': 25},
    {'field': 'specification', 'label': '规格型号', 'width': 150, 'type': 'readonly', 'excel_width': 20},
    {'field': 'material', 'label': '材质', 'width': 100, 'type': 'optional', 'excel_width': 12},
    {'field': 'surface_treatment', 'label': '表面处理', 'width': 100, 'type': 'optional', 'excel_width': 12},
    {'field': 'unit', 'label': '单位', 'width': 60, 'type': 'readonly', 'excel_width': 8},
    {'field': 'quantity', 'label': '数量', 'width': 80, 'type': 'required', 'excel_width': 10},
    {'field': 'drawing_no', 'label': '图纸号', 'width': 120, 'type': 'optional', 'excel_width': 15},
    {'field': 'weight', 'label': '重量(kg)', 'width': 80, 'type': 'optional', 'excel_width': 10},
]

# 电气BOM模板
ELECTRICAL_BOM_TEMPLATE = [
    {'field': 'index', 'label': '序号', 'width': 60, 'type': 'readonly', 'excel_width': 6},
    {'field': 'item_code', 'label': '物料编码', 'width': 120, 'type': 'required', 'excel_width': 15},
    {'field': 'elec_type', 'label': '电气类型', 'width': 100, 'type': 'optional', 'excel_width': 12,
     'options': ['PLC', 'HMI', '伺服', '变频器', '传感器', '开关', '继电器', '电源', '线缆', '其他']},
    {'field': 'item_name', 'label': '物料名称', 'width': 180, 'type': 'readonly', 'excel_width': 25},
    {'field': 'specification', 'label': '规格型号', 'width': 180, 'type': 'required', 'excel_width': 22},
    {'field': 'brand', 'label': '品牌', 'width': 100, 'type': 'required', 'excel_width': 12},
    {'field': 'unit', 'label': '单位', 'width': 60, 'type': 'readonly', 'excel_width': 8},
    {'field': 'quantity', 'label': '数量', 'width': 80, 'type': 'required', 'excel_width': 10},
    {'field': 'voltage', 'label': '电压', 'width': 80, 'type': 'optional', 'excel_width': 10},
    {'field': 'power', 'label': '功率', 'width': 80, 'type': 'optional', 'excel_width': 10},
    {'field': 'io_points', 'label': 'I/O点数', 'width': 80, 'type': 'optional', 'excel_width': 10},
]

# 气动BOM模板
PNEUMATIC_BOM_TEMPLATE = [
    {'field': 'index', 'label': '序号', 'width': 60, 'type': 'readonly', 'excel_width': 6},
    {'field': 'item_code', 'label': '物料编码', 'width': 120, 'type': 'required', 'excel_width': 15},
    {'field': 'pneu_type', 'label': '气动类型', 'width': 100, 'type': 'optional', 'excel_width': 12,
     'options': ['气缸', '电磁阀', '气源处理', '气管接头', '气动夹爪', '其他']},
    {'field': 'item_name', 'label': '物料名称', 'width': 180, 'type': 'readonly', 'excel_width': 25},
    {'field': 'specification', 'label': '规格型号', 'width': 180, 'type': 'required', 'excel_width': 22},
    {'field': 'brand', 'label': '品牌', 'width': 100, 'type': 'required', 'excel_width': 12},
    {'field': 'unit', 'label': '单位', 'width': 60, 'type': 'readonly', 'excel_width': 8},
    {'field': 'quantity', 'label': '数量', 'width': 80, 'type': 'required', 'excel_width': 10},
    {'field': 'bore_size', 'label': '缸径', 'width': 80, 'type': 'optional', 'excel_width': 10},
    {'field': 'stroke', 'label': '行程', 'width': 80, 'type': 'optional', 'excel_width': 10},
    {'field': 'pressure', 'label': '气压', 'width': 80, 'type': 'optional', 'excel_width': 10},
]

# 标准件BOM模板
STANDARD_PARTS_BOM_TEMPLATE = [
    {'field': 'index', 'label': '序号', 'width': 60, 'type': 'readonly', 'excel_width': 6},
    {'field': 'item_code', 'label': '物料编码', 'width': 120, 'type': 'required', 'excel_width': 15},
    {'field': 'std_type', 'label': '标准件类型', 'width': 100, 'type': 'optional', 'excel_width': 12,
     'options': ['螺丝螺母', '轴承', '导轨滑块', '丝杆螺母', '联轴器', '同步带轮', '其他']},
    {'field': 'item_name', 'label': '物料名称', 'width': 180, 'type': 'readonly', 'excel_width': 25},
    {'field': 'specification', 'label': '规格型号', 'width': 180, 'type': 'required', 'excel_width': 22},
    {'field': 'standard', 'label': '标准号', 'width': 100, 'type': 'optional', 'excel_width': 12,
     'options': ['GB', 'DIN', 'ISO', 'JIS', '厂标']},
    {'field': 'brand', 'label': '品牌', 'width': 100, 'type': 'optional', 'excel_width': 12},
    {'field': 'unit', 'label': '单位', 'width': 60, 'type': 'readonly', 'excel_width': 8},
    {'field': 'quantity', 'label': '数量', 'width': 80, 'type': 'required', 'excel_width': 10},
    {'field': 'material', 'label': '材质', 'width': 80, 'type': 'optional', 'excel_width': 10},
]

# 采购询价BOM模板
QUOTE_BOM_TEMPLATE = (
    BOM_CORE_FIELDS +
    [
        {
            'field': 'ref_price',
            'label': '历史单价(参考)',
            'width': 120,
            'type': 'ref',
            'excel_width': 14,
            'description': '历史采购单价参考',
        },
        {
            'field': 'ref_supplier',
            'label': '历史供应商(参考)',
            'width': 150,
            'type': 'ref',
            'excel_width': 18,
            'description': '历史供应商参考',
        },
        {
            'field': 'quote_supplier',
            'label': '供应商',
            'width': 150,
            'type': 'input',
            'excel_width': 18,
            'description': '填写供应商',
        },
        {
            'field': 'quote_price',
            'label': '含税单价',
            'width': 100,
            'type': 'input',
            'excel_width': 12,
            'description': '填写含税单价',
        },
        {
            'field': 'quote_delivery',
            'label': '交期(天)',
            'width': 80,
            'type': 'input',
            'excel_width': 10,
            'description': '填写交期天数',
        },
    ]
)

# CAD BOM导入字段映射（机械部分）
CAD_BOM_FIELD_MAPPING = {
    # CAD导入字段 -> 系统字段
    'part_number': 'item_code',
    'description': 'item_name',
    'file_name': 'cad_file_name',
    'quantity': 'quantity',
    'unit': 'unit',
    'material': 'material_spec',
    'weight': 'weight',
    'vendor': 'supplier_name',
    'revision': 'version_brand',
    'level': 'bom_level',
}

# 基础数据(物料主数据)表格 - 适用于所有物料类型
ITEM_MASTER_TABLE_COLUMNS = [
    {'field': 'index', 'label': '序号', 'width': 60},
    {'field': 'sku', 'label': '物料编码', 'width': 120},
    {'field': 'name', 'label': '物料名称', 'width': 180},
    {'field': 'item_category', 'label': '物料大类', 'width': 90},
    {'field': 'item_property', 'label': '物料属性', 'width': 90},
    {'field': 'specification', 'label': '规格型号', 'width': 150},
    {'field': 'brand', 'label': '品牌', 'width': 100},
    {'field': 'manufacturer', 'label': '生产厂家', 'width': 120},
    {'field': 'unit', 'label': '单位', 'width': 60},
    {'field': 'purchase_price', 'label': '采购单价', 'width': 100},
    {'field': 'sale_price', 'label': '销售单价', 'width': 100},
    {'field': 'standard_cost', 'label': '标准成本', 'width': 100},
    {'field': 'tax_rate', 'label': '税率(%)', 'width': 70},
    {'field': 'origin_country', 'label': '产地', 'width': 80},
    {'field': 'safety_stock', 'label': '安全库存', 'width': 80},
    {'field': 'lead_time', 'label': '采购周期(天)', 'width': 100},
    {'field': 'is_active', 'label': '状态', 'width': 70},
]


# =====================================================
# 辅助函数
# =====================================================

def get_excel_headers(field_config, include_required_mark=True):
    """生成Excel表头"""
    headers = []
    for f in field_config:
        label = f['label']
        if include_required_mark and f.get('type') == 'required':
            label = label.rstrip('*') + '*'
        headers.append((label, f.get('excel_width', 12), f.get('type', 'normal')))
    return headers


def get_field_mapping(field_config):
    """获取字段名称映射（用于导入时识别列名）"""
    mapping = {}
    for f in field_config:
        field_name = f['field']
        # 添加标准名称
        mapping[f['label']] = field_name
        mapping[f['label'].rstrip('*')] = field_name
        # 添加别名映射
        for alias in f.get('mapping', []):
            mapping[alias] = field_name
            mapping[alias.lower()] = field_name
            mapping[alias.upper()] = field_name
    return mapping


def get_table_columns(field_config):
    """生成前端表格列配置"""
    columns = []
    for f in field_config:
        col = {
            'prop': f['field'],
            'label': f['label'],
            'width': f.get('width', 100),
        }
        if f.get('type') == 'readonly':
            col['className'] = 'readonly-column'
        columns.append(col)
    return columns


# 导出统一配置供其他模块使用
BOM_FORMAT_CONFIG = {
    # 分类定义
    'item_category_l1': ITEM_CATEGORY_L1,
    'item_property': ITEM_PROPERTY,
    'mechanical_subcategory': MECHANICAL_SUBCATEGORY,
    'electrical_subcategory': ELECTRICAL_SUBCATEGORY,
    'pneumatic_subcategory': PNEUMATIC_SUBCATEGORY,
    
    # 字段定义
    'core_fields': BOM_CORE_FIELDS,
    'purchase_fields': BOM_PURCHASE_FIELDS,
    'inventory_fields': BOM_INVENTORY_FIELDS,
    'cost_fields': BOM_COST_FIELDS,
    'requirement_fields': BOM_REQUIREMENT_FIELDS,
    'process_fields': BOM_PROCESS_FIELDS,
    'drawing_fields': BOM_DRAWING_FIELDS,
    'technical_fields': BOM_TECHNICAL_FIELDS,
    
    # 全局BOM模板
    'project_bom_table': PROJECT_BOM_TABLE_COLUMNS,
    'project_bom_import': PROJECT_BOM_IMPORT_TEMPLATE,
    'project_bom_export': PROJECT_BOM_EXPORT_COLUMNS,
    'quote_bom': QUOTE_BOM_TEMPLATE,
    
    # 分类BOM模板
    'mechanical_bom': MECHANICAL_BOM_TEMPLATE,      # 机械类（CAD导入用）
    'electrical_bom': ELECTRICAL_BOM_TEMPLATE,      # 电气类
    'pneumatic_bom': PNEUMATIC_BOM_TEMPLATE,        # 气动类
    'standard_parts_bom': STANDARD_PARTS_BOM_TEMPLATE,  # 标准件
    
    # 物料主数据
    'item_master': ITEM_MASTER_TABLE_COLUMNS,
    
    # CAD导入映射（仅机械部分）
    'cad_mapping': CAD_BOM_FIELD_MAPPING,
}
