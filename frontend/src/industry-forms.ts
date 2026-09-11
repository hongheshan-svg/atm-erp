import type { Command, Field } from './types'

// Presentation only: keep original field keys, permissions, defaults and payload preparation.
// Context-specific guidance belongs to the business operation, never to a new data store.
const guidance: Record<string, Partial<Field>> = {
  requirements: { type: 'textarea', wide: true, placeholder: '加工产品与样件：\n工艺 / 节拍 / 精度：\n工位与设备范围：\n电源、气源及现场接口：\n验收标准与交付资料：', hint: '填写双方已确认的指标；未确认项注明待确认。技术协议、布局图及版本文件从单据附件上传。' },
  specification: { placeholder: '完整订货型号、材质、尺寸及表面处理', hint: '产品型号/规格与图号、图档版本分别填写；品牌不用于存放版本。选择产品编码类别后型号/规格必填。' },
  brand: { placeholder: '填写指定品牌；未指定可留空', hint: '标准件按确认品牌填写，替代品牌需先确认；不要用供应商名称代替品牌。' },
  part_type: { hint: '标准件用于外购选型件；非标件用于按图加工件。分类会用于 BOM 筛选采购。' },
  unit: { placeholder: '如 件、套、米、千克', hint: '库存、BOM、采购共用此计量单位；包装数量须先换算，系统不自动做单位换算。' },
  assembly_unit: { placeholder: '如 上料单元、视觉检测单元、下料单元', hint: '同一项目统一单元名称，便于分单元选料、采购及交付配套。' },
  change_note: { type: 'textarea', wide: true, placeholder: '变更依据 / 图纸版本、变更内容、受影响工位及旧料处理方式' },
  equipment_quantity: { numeric: { scale: 0, min: 1 }, hint: '填写合同约定的整机 / 整线交付数量；工位数和 BOM 用料数量另行维护。' },
  warranty_months: { numeric: { scale: 0, min: 0, max: 120 }, hint: '通常为 12 个月，按合同填写；各批次从验收日起计算，0 表示无质保。' },
  location: { placeholder: '如 主仓-A区-02架', hint: '按实际存放位置填写，同一库位保持一致命名。' },
  delivery_address: { type: 'textarea', wide: true, placeholder: '省市区、厂区 / 楼栋、收货联系人及电话', hint: '填写双方确认的实际交货地点，并核对与签署合同一致。' },
  account: { placeholder: '如 公司基本户 / 银行名称与尾号', hint: '与银行记录使用一致的账户标识，便于后续匹配。' },
  reference: { placeholder: '按银行回单填写，保留前导零', hint: '填写实际交易流水号，不使用采购单号或合同号代替。' },
  counterparty: { placeholder: '银行回单上的完整对方户名' },
  basis: { type: 'textarea', wide: true, placeholder: '合同编号、付款节点、比例 / 金额及触发条件' },
  hourly_cost: { numeric: { scale: 2, min: 0 }, hint: '用于项目人工成本核算的含税经营成本口径；按企业核算标准维护，录入工时时固化成本。' },
  payment_days: { numeric: { scale: 0, min: 0, max: 365 } },
  padding: { numeric: { scale: 0, min: 1, max: 10 }, hint: '流水数字位数，不含前缀和日期；正式使用前核对编号样例。' },
  prefix: { placeholder: '如 MAT-、PO-，按公司编码规则填写' },
  file: { hint: '建议命名：单据号_资料名称_版本_日期。上传签署合同、图纸或验收记录；新版本保留原文件。' },
}

export function industryCommand(command: Command): Command {
  if (command.readonly) return command
  const path = command.path
  const purchase = path.startsWith('/business/purchases/')
  const sales = path.startsWith('/business/sales/')
  const projects = path.startsWith('/business/projects/')
  const bom = path.includes('revise-bom')
  const visit = (fields: Field[], nested = false): Field[] => fields.map(field => {
    if (field.hidden || field.displayOnly || (field.readonly && field.type !== 'rows')) return field
    const key = field.key
    let extra: Partial<Field> = { ...guidance[key] }
    if (['reason', 'note', 'description', 'response', 'duplicate_reason'].includes(key)) extra = { ...extra, type: 'textarea', wide: true }
    if (key === 'reason') extra.placeholder = '说明业务依据、处理内容及相关单据 / 图纸版本，便于后续追溯'
    if (key === 'reason' && path.startsWith('/business/deliveries/') && path.endsWith('/accept/')) extra = { ...extra, placeholder: '验收依据 / 记录编号、节拍与精度实测、连续运行结果、遗留项及客户确认情况', hint: '先上传客户确认的验收记录；验收会推进项目状态并起算本批质保。' }
    if (key === 'reason' && path.startsWith('/business/tasks/') && path.endsWith('/complete/')) extra.placeholder = '完成内容、图纸 / 程序版本、测试结果及交接记录；未解决事项请如实说明'
    if (key === 'reason' && path.includes('/forecast/')) extra.placeholder = '剩余外购与加工件、机械 / 电气 / 软件调试工时、差旅及运输费用的估算依据'
    if (key === 'address') extra = { ...extra, wide: true, placeholder: '完整省市区、街道及厂区 / 楼栋', hint: '用于合同主体资料；采购实际收货地址在签署版本归档时另行确认。' }
    if (key === 'username') extra = { ...extra, placeholder: '如 zhangsan、lisi，按公司账号规范填写', hint: '一人一个账号；兼任岗位请在同一账号多选角色，便于操作追溯。' }
    if (key === 'members') extra.hint = '选择参与机械、电气、软件、装配及调试的实际人员；后续任务仍需指定执行人。'
    if (key === 'name' && (sales || projects)) extra.placeholder = '如 客户简称 · 产品型号 · 自动装配检测线'
    if (key === 'name' && path.startsWith('/business/items/')) extra.placeholder = '如 伺服电机、光电传感器、定位治具底板'
    if (key === 'name' && path.startsWith('/business/partners/')) extra.hint = '使用合同及开票的完整单位名称，避免同一往来单位重复建档。'
    if (key === 'code' && path.startsWith('/business/items/')) extra = { ...extra, placeholder: '填写公司物料编码；留空自动生成', hint: '支持自定义编码，保留前导零；同一规格优先复用已有物料。' }
    if (key === 'item') extra.hint = '核对编码、规格、品牌和单位；同名不同型号不可混用。'
    if (key === 'title' && path.startsWith('/business/tasks/')) extra.placeholder = '如 机械图纸评审、电柜接线、节拍联调与连续运行测试'
    if (key === 'description' && path.startsWith('/business/tasks/')) extra.placeholder = '所属单元、工作内容、图纸 / 程序版本、完成标准及交接资料'
    if (key === 'description' && (purchase || path.includes('service'))) extra.placeholder = '设备 / 物料、批次或序列号、故障现象、现场条件、排查结果及处理要求'
    if (key === 'note' && purchase) extra = { ...extra, placeholder: '图号 / 版本、材质及处理要求、检验标准、随货资料、包装和其他约定', hint: '此说明会进入采购合同补充约定；只填写双方需要确认的内容。' }
    if (key === 'note' && path.includes('/ship/')) extra.placeholder = '设备编号、包装件数、配套清单、运输与现场安装安排'
    if (key === 'title' && nested && sales) extra.placeholder = '如 预付款、发货款、验收款、质保尾款'
    if (key === 'title' && path.includes('/expense/')) extra = { ...extra, placeholder: '如 客户现场安装差旅、设备运输、外协调试', hint: '仅登记项目费用，采购材料和工时人工已由原业务计入，避免重复记成本。' }
    if (key === 'due_date') extra.hint = purchase ? (nested ? `${field.optional ? '留空沿用订单交期；' : ''}关键长交期件按供应商确认日期填写。` : '填写供应商确认的交货日期；付款到期日按采购账期独立计算。') : '按合同或执行计划填写；未确认的选填日期可留空。'
    if (key === 'date') extra.hint = '填写实际业务发生日期；跨期补录请核对锁账范围。'
    if (key === 'received_date') extra.hint = '按实际合格收货日填写，作为库存入库及采购账期起算依据。'
    if (key === 'quantity' || key === 'pending_quantity') {
      extra.numeric = { scale: 3, min: 0 }
      extra.hint = bom ? '整个项目本单元的总需求，含全部设备；系统不会再乘设备台数。' : '按所选物料的基础单位填写，最多 3 位小数。'
      if (projects && path.includes('/ship/') && !nested) extra = { ...extra, numeric: { scale: 0, min: 1 }, hint: '本批实际发出的整机 / 整线数量，不是包装件数或物料数量。' }
      if (purchase && path.includes('/receive/')) extra.hint = key === 'quantity' ? '本次合格入库数量；不合格品填写到隔离数量，两者合计为本次到货量。' : '本次不合格 / 待检隔离数量，不进入可用库存；全合格填 0。'
      if (path.includes('/count/')) extra.hint = '填写现场实点总数量，不填盘盈盘亏差额；实盘为零时填 0。'
    }
    if (field.type !== 'rows' && ['amount', 'unit_price', 'unit_cost', 'fee', 'approved_amount', 'counterparty_balance', 'materials', 'labor', 'expenses', 'remaining_materials', 'remaining_labor', 'remaining_expenses'].includes(key)) {
      const signed = key === 'counterparty_balance' || (key === 'amount' && path === '/business/bank-records/')
      extra.numeric = { scale: 2, ...(signed ? { signed: true } : { min: 0 }) }
      if (!extra.hint) extra.hint = '人民币 CNY 含税金额，最多 2 位小数；按实际业务填写。'
      if (signed) extra.hint = key === 'amount' ? '按银行实际发生额填写：收入为正、支出为负；不填写余额。' : '填写对方核对后的余额；待退款为负数，与系统余额核对差异。'
    }
    if (key === 'hours') extra = { ...extra, numeric: { scale: 2, min: 0, max: 24 }, hint: '实际投入当前任务的小时数，最多 2 位小数；多人分别登记，同一天不要重复填报。' }
    // Explicit business field descriptions take precedence over shared guidance.
    return { ...extra, ...field, fields: field.fields ? visit(field.fields, true) : undefined }
  })
  return { ...command, fields: visit(command.fields) }
}
