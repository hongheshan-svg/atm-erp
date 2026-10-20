"""One employee-facing guide shared by template downloads and import dialogs."""

import io
from html import escape

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework.exceptions import ValidationError

from ..models import Item
from .tabular import document

GUIDE_SHEET = '填写说明'
GUIDE_MARKER = 'ERP导入模板填写说明'
COMMON = [
    '只在“数据”页第2行起填写，一行一条明细；保留表头名称和顺序。填写说明不参与导入，请勿在说明页填业务数据。',
    '说明中的姓名、账号、编码、ID和日期均为格式示例，必须换成实际值；示例不代表系统中已有记录。',
    '最多1000条数据、5MB。Excel可保留系统附带的填写说明页；不要增加其他工作表。旧版单工作表模板仍可用。',
    '日期填写YYYY-MM-DD，例如2026-10-20。不能填写20天、20或46290等普通数字；Excel日期单元格请设置为日期格式。',
    '人员可填姓名或登录账号，重名请填姓名（用户名）；编码、账号、电话、流水号按文本填写，保留前导零，不要把编号与记录ID混用。',
    '金额使用人民币含税金额，最多2位小数；数量最多3位小数。只填数值，不加元、件、千分位或计算公式。',
    'CSV使用UTF-8编码，只保存数据页；CSV不能附带说明，请另行下载填写说明。Excel打开CSV时注意编码与长数字按文本读取。',
    '上传后先检查预览，再确认导入；任一行失败整批不保存。不要重复上传已经确认成功的文件，避免重复新增。',
]

# title, entry, purpose / prerequisites. These are documentation, not alternative validation rules.
RESOURCES = {
    'items': (
        '物料',
        '基础资料 → 物料 → 导入导出 → 导入',
        '新增物料，不覆盖已有物料。编码可自定义或留空自动生成；相同物料优先复用，确需独立建码应填写原因。',
    ),
    'partners': (
        '往来单位',
        '基础资料 → 往来单位 → 导入导出 → 导入',
        '新增客户、供应商或双用途往来单位，编号自动生成。采购账期只适用于供应商；销售经理单岗只能新增纯客户。',
    ),
    'sales': (
        '销售',
        '销售 → 导入导出 → 导入',
        '新增销售草稿，后续仍需报价和签约。仅销售经理权限时，负责人填写本人姓名或账号。',
    ),
    'projects': (
        '项目',
        '项目 → 项目列表 → 导入导出 → 导入',
        '新增执行项目。已签约销售请通过销售签约生成项目，避免重复；此入口不能导入任务或BOM。',
    ),
    'purchases': (
        '采购',
        '采购 → 导入导出 → 导入',
        '同一分组号的行合为一张采购草稿，仍需提交审批。同组的项目、供应商、交期、账期和说明必须一致；同组物料不能重复。'
        '该模板不关联BOM行；需要按BOM单元下单时请使用“从BOM多选下单”。',
    ),
    'tasks': (
        '项目任务',
        '打开对应项目 → 任务与工时 → 项目任务 → 导入导出 → 导入',
        '只新增设计、装配、调试任务，项目须为执行中或交付中。采购在采购模块办理，发货在交付模块办理；'
        '安装和验收任务随发货创建，售后从交付批次创建。T0、T1等编号不是阶段选项。',
    ),
    'stocks': (
        '期初库存',
        '库存 → 现有库存 → 导入导出 → 导入',
        '仅管理员录入期初库存，只允许尚无库存流水的物料和库位；已有库存请使用盘点，不可重复导入期初。',
    ),
    'entries': (
        '项目费用',
        '收付款 → 应收应付与费用 → 导入导出 → 导入',
        '仅新增项目费用。合同应收、采购应付由原单据产生，不要通过此模板重复登记；项目须为执行中、交付中或质保阶段。',
    ),
    'payments': (
        '收付款记录',
        '收付款 → 收付款流水 → 导入导出 → 导入',
        '对已有款项登记正常收付款，金额须为正且不超过可收付余额。采购付款需要有效已确认对账单；'
        '退款、冲销从原记录操作。导入不发起银行转账。',
    ),
    'time': (
        '工时',
        '打开对应项目 → 任务与工时 → 工时记录 → 导入导出 → 导入',
        '为已有任务登记工时，不创建任务。任务须为待完成或已完成；人员须在项目范围内。'
        '普通成员只能登记本人任务的本人工时，管理岗位仍按任务管理范围校验。',
    ),
    'deliveries': (
        '发货',
        '打开对应项目 → 交付与售后 → 导入导出 → 导入',
        '登记实际发货并创建安装、验收任务。设计、装配、调试任务须全部完成，BOM及领料须满足本批交付。'
        '多单元项目请从页面发货并明确本批配套物料，不能用此模板省略配套清单。',
    ),
    'moves': (
        '项目领料',
        '库存 → 库存流水 → 导入导出 → 导入',
        '登记项目领料，数量不能超过库存及BOM剩余需求；退料、退货从原流水操作。'
        '需要确认占用其他项目到货时，请改用页面领料并核对提示。',
    ),
    'bom': (
        'BOM',
        'BOM → 选择项目 → 导入预览；也可在项目详情的BOM页操作',
        '已有物料填写系统物料编码，后方物料资料可以留空；填写时必须与现有资料一致，不会覆盖主数据。'
        '新增物料编码留空，填写名称、规格、产品编码类别和单位；有图产品再填图号。'
        '完全相同物料自动复用；多个匹配须明确编码，新编号只在确认后生成。'
        '同一文件中“物料编码＋单元”不能重复，空单元也算同一单元；先核实重复粘贴、独立用量或不同单元，不能盲目累加。',
    ),
}

PERSON_HINT = '可填姓名或登录账号；重名或姓名与他人账号相同时，填写姓名（用户名）明确人员。'
DATE_HINT = '填写具体日期YYYY-MM-DD，不是天数，也不能填Excel日期序号。'
PRODUCT_HINT = '；'.join(f'{value}＝{label}' for value, label in Item.ProductCategory.choices) + (
    '。可填上述编码或完整中文名称，不能填1或2；与“物料类别”的标准件/非标件不是同一分类。'
)

# required, hint, example. Every schema key must have an explicit description.
FIELDS = {
    'name': ('必填', '填写名称，不填写系统编号。', '输送线支架'),
    'code': (
        '可空',
        '新增物料可自定义唯一编码，最多30字符；留空自动生成。已用编码（含停用或已删除）不能重复使用。',
        'MAT-001',
    ),
    'specification': ('条件必填', '填写产品编码类别时必填型号/规格；不能用图号替代。最多2000字符。', 'HGW20CC'),
    'drawing_number': (
        '条件必填',
        '产品编码类别为11/12/13/19时必填图号。与型号/规格分别填写，最多100字符。',
        'A2608-01-P001',
    ),
    'drawing_revision': ('可空', '填写实际图档版本，最多30字符；没有版本可留空。不要填写PCS、品牌或数量。', 'A'),
    'product_category': ('可空', PRODUCT_HINT, '无图·标准件'),
    'brand': ('可空', '填写品牌，最多80字符；不要填写图档版本。', '上银'),
    'part_type': ('可空', '填写标准件或非标件（兼容standard/custom）。机加、钣金应填在产品编码类别中。', '标准件'),
    'unit': ('可空，默认件', '填写计量单位，不要填入图档版本列；同一物料沿用其原单位。', 'PCS'),
    'duplicate_reason': (
        '条件必填',
        '相同名称、规格等资料的物料确需独立建码时，填写真实原因；不覆盖原物料。',
        '客户要求单独管理',
    ),
    'contact': ('可空', '填写业务联系人姓名。', '张工'),
    'phone': ('可空', '按文本填写电话，保留区号和前导零。', '0571-12345678'),
    'address': ('可空', '填写联系或收货地址。', '杭州市某路1号'),
    'customer': ('必填', '填写基础资料中已启用客户或双用途单位的编码，不能填写客户名称或记录ID。', 'C001'),
    'supplier': ('必填', '填写基础资料中已启用供应商或双用途单位的编码，不能填写名称或记录ID。', 'S001'),
    'manager': ('必填', PERSON_HINT + '人员须已启用。', '刘经理'),
    'requirements': ('可空', '填写需求内容，最多20000字符。', '输送后自动定位并焊接'),
    'due_date': ('可空', DATE_HINT, '2026-10-20'),
    'equipment_quantity': ('可空，默认1', '填写大于0的整数，单位为台。', '1'),
    'warranty_months': ('可空，默认12', '填写0～120的整数，单位为月。', '12'),
    'members': ('可空', PERSON_HINT + '多个成员用分号（;或；）分隔，人员须已启用。', '张工;李工'),
    'group': ('必填', '同一采购草稿使用同一分组号；不同采购单用不同分组号，不是系统采购编号。', 'G001'),
    'project': (
        '必填',
        '填写可操作的执行项目编号，不填名称或记录ID。文件编号决定归属，不自动使用当前页面筛选的项目。',
        'ATM2601',
    ),
    'item': ('必填', '填写已启用物料的系统编码，不能填名称、图号或记录ID。', 'MAT-001'),
    'quantity': ('必填', '填写大于0的数量，最多3位小数，不加单位文字。', '2.125'),
    'unit_price': ('必填', '填写大于或等于0的人民币含税单价，最多2位小数；不填未税价或整行总额。', '120.50'),
    'line_due_date': ('可空', DATE_HINT + '留空沿用该采购单交期。', '2026-10-20'),
    'payment_term': (
        '可空',
        '填写指定日期、现付、月结30天、月结60天、月结90天、月结120天、自定义月结；'
        '兼容manual/cash/month30/month60/month90/month120/custom。月结按收货当月月底加天数。',
        '月结30天',
    ),
    'payment_days': ('自定义月结时填写', '填写0～365的整数，仅用于自定义月结，其他账期请留空。', '45'),
    'payment_due_date': ('可空', DATE_HINT + '仅指定日期账期可填；自动账期必须留空，按实际收货计算。', '2026-10-20'),
    'note': ('可空', '填写本单据的补充说明。', '按约定交付'),
    'title': ('必填', '填写任务的具体名称，最多150字符。', '机械设计'),
    'description': ('可空', '填写任务工作内容，最多20000字符。', '完成装配图并校核'),
    'assignee': ('必填', PERSON_HINT + '须已启用且属于该项目的负责人或可访问成员。', '张工'),
    'location': ('可空，默认主仓', '填写库位名称；期初允许建立新库位，同物料不同库位分别填行。', '主仓'),
    'unit_cost': ('必填', '填写大于或等于0的单位成本，人民币含税，最多2位小数，不填库存总金额。', '20.00'),
    'reason': ('必填', '填写实际业务原因或工作内容。', '期初盘点录入'),
    'amount': ('必填', '填写大于0的人民币含税金额，最多2位小数，不带货币符号或千分位。', '100.00'),
    'entry': ('必填', '从应收应付列表导出获取款项的记录ID，不填项目编号或款项名称。', '123'),
    'date': ('必填', DATE_HINT + '填写实际发生日期，不能晚于今天。', '2026-10-19'),
    'method': ('可空，默认银行转账', '填写银行转账、现金、其他（兼容bank/cash/other）。', '银行转账'),
    'account': ('可空', '填写收付账户标识，按文本保留前导零。', '基本户'),
    'reference': ('可空', '填写银行流水号，按文本保留完整号码，不用Excel科学计数法。', '000012345678'),
    'document': ('可空', '填写已上传的同项目收付凭证记录ID，不填文件名或文件路径。', '456'),
    'reconciliation': ('采购付款必填', '填写已确认且仍有效的同款项对账单ID；客户收款、项目费用可留空。', '789'),
    'task': ('必填', '从项目任务列表导出获取任务记录ID，不填任务名称或项目编号。', '101'),
    'user': ('可空，默认本人', PERSON_HINT + '须已启用且在项目范围内。', '张工'),
    'hours': ('必填', '填写大于0的小时数，最多2位小数；同一人员同一天累计净工时不能超过24小时。', '7.50'),
    'installer': ('可空，默认项目负责人', PERSON_HINT + '安装人员须已启用且属于该项目。', '张工'),
    'acceptor': ('可空，默认项目负责人', PERSON_HINT + '验收人员须已启用且属于该项目。', '刘经理'),
    'stock': ('必填', '从共享库存列表导出获取库存记录ID，代表具体物料和库位，不是物料编码。', '202'),
    'assembly_unit': (
        '可空',
        '填写实际装配单元，最多100字符。同料可分属不同单元；相同编码和单元不可重复，空单元也会判重。',
        '上料单元',
    ),
    'change_note': ('修改已有BOM时必填', '填写变更原因，最多500字符；新行可空，不是物料备注。', '设计变更，增加支撑件'),
    'required_date': ('可空', DATE_HINT + '表示物料需求日期。', '2026-10-20'),
    'application_date': ('可空', DATE_HINT + '表示申请日期。', '2026-10-19'),
    'applicant': ('可空', '填写纸面申请人姓名，最多80字符；本列不是任务的执行人账号。', '张工'),
}

OVERRIDES = {
    ('items', 'name'): ('必填', '填写物料名称，不填写编码或规格。', '滑块'),
    ('partners', 'name'): ('必填', '填写往来单位名称，不填写联系人姓名。', '示例机械有限公司'),
    ('sales', 'name'): ('必填', '填写本笔销售业务名称，最多150字符。', '输送线设备销售'),
    ('projects', 'name'): ('必填', '填写执行项目名称，最多150字符；项目编号自动生成。', '输送线改造项目'),
    ('partners', 'kind'): ('必填', '填写客户、供应商、客户及供应商（兼容customer/supplier/both）。', '供应商'),
    ('partners', 'payment_term'): (
        '可空，默认指定日期',
        FIELDS['payment_term'][1] + '纯客户留空或填指定日期。',
        '月结30天',
    ),
    ('purchases', 'payment_term'): ('可空，沿用供应商账期', FIELDS['payment_term'][1], '月结30天'),
    ('purchases', 'due_date'): ('必填', DATE_HINT + '表示整张采购单交期，同组保持一致。', '2026-10-20'),
    ('projects', 'manager'): ('必填', FIELDS['manager'][1] + '须具备项目经理或管理员岗位。', '刘经理'),
    ('sales', 'manager'): ('必填', FIELDS['manager'][1] + '须具备销售经理、项目经理或管理员岗位。', '刘经理'),
    ('tasks', 'kind'): (
        '必填',
        '填写设计、装配、调试（兼容design/assembly/test）。不能填T0/T1/T2/T3、采购或发货。',
        '设计',
    ),
    ('tasks', 'due_date'): ('可空', DATE_HINT + '“期限”表示截止日期，不是工期天数。', '2026-10-20'),
    ('entries', 'due_date'): ('必填', DATE_HINT + '表示费用付款到期日。', '2026-10-20'),
    ('entries', 'title'): ('必填', '填写项目费用名称；不能用来新增合同应收或采购应付。', '项目差旅费'),
    ('time', 'reason'): ('必填', '填写当日实际工作内容。', '完成机械装配图'),
    ('payments', 'reason'): ('必填', '填写本次实际收付款说明。', '支付项目差旅费'),
    ('moves', 'reason'): ('必填', '填写实际领料用途。', '装配领料'),
    ('moves', 'task'): ('条件必填', '可关联同项目未完成任务。已验收项目领料必须填未完成的售后任务ID。', '101'),
    ('deliveries', 'quantity'): ('必填', '填写大于0的设备台数整数，不能超过项目剩余未发货台数。', '1'),
    ('bom', 'code'): (
        '已有物料必填；新增留空',
        '已有编码必须在系统中存在且启用；后方物料资料可空，填了须与主数据一致。'
        '新增物料请留空，不能直接填外部系统的未建档编码。',
        'MAT-001',
    ),
    ('bom', 'name'): ('新增物料必填', '编码留空时填写物料名称；已有物料可空，填写时须与系统一致。', '滑块'),
    ('bom', 'specification'): ('新增物料必填', '编码留空时必须填写型号/规格，即使已填写图号也不能省略。', 'HGW20CC'),
    ('bom', 'drawing_number'): (
        '新增有图物料必填',
        '新建11/12/13/19类物料时填写图号，最多100字符；已有物料可空，填写时须与系统一致。',
        'A2608-01-P001',
    ),
    ('bom', 'product_category'): ('新增物料必填', PRODUCT_HINT, '无图·标准件'),
    ('bom', 'unit'): ('新增物料必填', '填写计量单位；已有物料可空，填写时须与系统一致。', 'PCS'),
}

BOM_COLUMNS = [
    ('物料编码', 'code'),
    ('单元', 'assembly_unit'),
    ('需求数量', 'quantity'),
    ('变更说明', 'change_note'),
    ('需求日期', 'required_date'),
    ('申请日期', 'application_date'),
    ('申请人', 'applicant'),
    ('物料名称', 'name'),
    ('规格', 'specification'),
    ('图号', 'drawing_number'),
    ('图档版本', 'drawing_revision'),
    ('产品编码类别', 'product_category'),
    ('品牌', 'brand'),
    ('物料类别', 'part_type'),
    ('单位', 'unit'),
]


def guide(resource, columns):
    title, entry, note = RESOURCES[resource]
    fields = []
    for label, key in columns:
        required, hint, example = OVERRIDES[(resource, key)] if (resource, key) in OVERRIDES else FIELDS[key]
        fields.append({'key': key, 'label': label, 'required': required, 'hint': hint, 'example': example})
    return {'title': title, 'entry': entry, 'note': note, 'instructions': COMMON, 'columns': fields}


def html_guide(layout):
    fields = ''.join(
        '<tr>'
        + ''.join(f'<td>{escape(column[key])}</td>' for key in ('label', 'required', 'hint', 'example'))
        + '</tr>'
        for column in layout['columns']
    )
    rules = ''.join(f'<li>{escape(rule)}</li>' for rule in layout['instructions'])
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(layout["title"])}导入模板填写说明</title>'
        '<style>body{font:16px/1.7 system-ui,sans-serif;color:#233044;max-width:1100px;margin:32px auto;padding:0 20px}'
        'h1{font-size:26px}li{margin:8px 0}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd5df;'
        'padding:12px;text-align:left;vertical-align:top}th{background:#edf3f8}td:first-child{min-width:100px}'
        '.table{overflow:auto}@media print{body{font-size:11px;margin:0}thead{display:table-header-group}'
        'tr{break-inside:avoid}}</style>'
        f'<h1>{escape(layout["title"])}导入模板填写说明</h1>'
        f'<p><strong>导入入口：</strong>{escape(layout["entry"])}</p><p>{escape(layout["note"])}</p>'
        f'<h2>填写前请阅读</h2><ol>{rules}</ol>'
        '<h2>逐列填写说明</h2><p>示例仅说明格式，请替换为真实业务数据。</p><div class="table"><table>'
        '<thead><tr><th>模板字段</th><th>是否必填</th><th>填写规则</th><th>格式示例</th></tr></thead>'
        f'<tbody>{fields}</tbody></table></div></html>'
    )


def template_document(name, layout, file_format):
    headers = [column['label'] for column in layout['columns']]
    if file_format == 'csv':
        return document(name, headers, [], 'csv')
    if file_format == 'html':
        response = HttpResponse(html_guide(layout), content_type='text/html; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{name}-guide.html"'
    elif file_format == 'xlsx':
        book = Workbook()
        data = book.active
        data.title = '数据'
        data.append(headers)
        data.freeze_panes = 'A2'
        data.sheet_properties.pageSetUpPr.fitToPage = True
        fill = PatternFill('solid', fgColor='E8F0F8')
        for index, column in enumerate(layout['columns'], 1):
            header = data.cell(1, index)
            header.font = Font(bold=True, color='233044')
            header.fill = fill
            header.comment = Comment(
                f'{column["required"]}\n{column["hint"]}\n格式示例：{column["example"]}\n完整说明见“填写说明”页。',
                '项目ERP',
            )
            data.column_dimensions[get_column_letter(index)].width = max(18, len(column['label']) * 2 + 2)
        help_sheet = book.create_sheet(GUIDE_SHEET)
        help_sheet.append([GUIDE_MARKER])
        help_sheet.append([f'{layout["title"]}导入模板'])
        help_sheet.append(['导入入口', layout['entry']])
        help_sheet.append(['用途与前提', layout['note']])
        for rule in layout['instructions']:
            help_sheet.append(['通用说明', rule])
        help_sheet.append(['模板字段', '是否必填与填写规则', '格式示例（请替换为真实值）'])
        for column in layout['columns']:
            help_sheet.append([column['label'], f'{column["required"]}。{column["hint"]}', column['example']])
        for row in help_sheet:
            for value in row:
                value.alignment = Alignment(vertical='top', wrap_text=True)
                value.font = Font(name='等线', size=11, color='233044')
            lines = max(len(str(value.value or '')) // width for value, width in zip(row, (12, 42, 18), strict=True))
            help_sheet.row_dimensions[row[0].row].height = max(36, 18 * (1 + lines))
        for letter, width in [('A', 24), ('B', 86), ('C', 38)]:
            help_sheet.column_dimensions[letter].width = width
        for row in (1, 2, 5 + len(layout['instructions'])):
            for value in help_sheet[row]:
                value.fill = fill
                value.font = Font(bold=True, color='233044')
        help_sheet.freeze_panes = 'B5'
        help_sheet.sheet_properties.pageSetUpPr.fitToPage = True
        help_sheet.page_setup.orientation = 'landscape'
        help_sheet.page_setup.paperSize = help_sheet.PAPERSIZE_A4
        help_sheet.page_setup.fitToWidth = 1
        help_sheet.page_setup.fitToHeight = 0
        output = io.BytesIO()
        book.save(output)
        book.close()
        response = HttpResponse(
            output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{name}.xlsx"'
    else:
        raise ValidationError({'file_format': '请选择csv、xlsx或html填写说明。'})
    response['Cache-Control'] = 'no-store'
    return response
