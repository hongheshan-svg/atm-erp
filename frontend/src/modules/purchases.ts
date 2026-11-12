import { codeField } from './shared'
import { materialDetails, warehouseLines } from './warehouse-lines'
import { item } from './shared'
import { project } from './shared'
import { remote } from './shared'
import { date } from './shared'
import { termFields, termLabel } from './payment-terms'
// 未关联 BOM 行的物料超出本项目缺口（BOM 需求 − 已领 / 已到货 − 在途）时，服务端要求写明原因并在审批时提示。
const overBomReason: Field = {
  key: 'over_bom_reason', label: '超 BOM 采购原因', type: 'textarea', optional: true,
  placeholder: '仅超出项目 BOM 缺口时填写，如备件、损耗补买、客户追加',
  hint: '按 BOM 补缺请用「从 BOM 多选下单」。本单物料超出项目 BOM 缺口时必须填写，审批人会看到超出数量和原因。',
}
export const purchaseFields = (): Field[] => [
  codeField('采购单号'),
  project(),
  remote('supplier', '供应商', '/business/partners/', {
    remoteParams: { is_active: true },
    remoteFilter: p => p.kind !== 'customer',
    remoteLabel: p => `${p.code} · ${p.name} · ${termLabel(p)}`,
  }),
  date('due_date', '交期'),
  ...termFields(true),
  { ...date('payment_due_date', '付款到期日'), optional: true, initial: '', hint: '仅指定日期账期填写；现付/月结请留空，实际到期明细在应收应付中查看。历史手工账期留空仍沿用订单交期。' },
  t('note', '说明', true),
  overBomReason,
  { key: 'warranty_months', label: '供应商质保月数', initial: '12', numeric: { scale: 0, min: 1, max: 120 }, hint: '按每批合格收货日起算，写入采购合同质保条款；默认 12 个月。' },
  rows('lines', '采购明细', [item(), { ...qty, numeric: { scale: 3, min: 0.001 } }, price, { ...date('due_date', '明细交期'), optional: true }]),
]
import { all, read } from '../api'
import { purchaseApprover } from '../session'
import { contractReader, money } from '../session'
import { money as formatMoney } from '../utils/money'
import { quantityText } from '../utils/quantity'
import { dateTimeText } from '../utils/datetime'
import { decimalDifference } from '../forms'
import { fromScaled, QUANTITY_SCALE, toScaled } from '../utils/decimal'
import { formatPurchaseAmount, purchaseLineCents } from '../bom-purchase'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { select } from './shared'
import { rows } from './shared'
import { reason } from './shared'
import { optionalReason } from './shared'
import { projectLink } from './shared'
import { qty } from './shared'
import { price } from './shared'
import { buyer } from './shared'
import { warehouse } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
import { display } from './shared'
export function receiptStatus(row: Row): string {
  if (row.change_request) return '修改申请待处理'
  const pending = (row.lines || []).reduce((sum: bigint, line: Row) => sum + (toScaled(line.pending_quantity || '0', QUANTITY_SCALE) ?? 0n), 0n)
  if (!pending) return display(row.status)
  const arrivedOnly = !(row.lines || []).some((line: Row) => Number(line.received_quantity || 0) > 0)
  return `${arrivedOnly ? '已到货待检' : display(row.status)} · 隔离 ${fromScaled(pending, QUANTITY_SCALE)}`
}
// 明细合计只作展示：与服务端同口径，逐行按分四舍五入后再相加；任一行没有单价（无权查看）时不给合计。
export function purchaseTotal(lines: Row[]): string {
  if (!lines.length || lines.some(line => line.unit_price == null || line.unit_price === '')) return '—'
  const cents = lines.map(line => purchaseLineCents(line.quantity, line.unit_price))
  if (cents.some(value => value == null)) return '—'
  return formatPurchaseAmount(cents.reduce((sum: bigint, value) => sum + value!, 0n))
}
export const columns: Record<string, Column[]> = {
  purchases: [
    C('code', '采购编号'),
    { key: 'project_name', label: '项目', link: projectLink },
    C('supplier_name', '供应商'),
    // 含税合计按明细汇总；无单价权限（仓管）时显示「—」。
    { key: 'total', label: '含税合计（元）', format: row => purchaseTotal(row.lines || []) },
    { key: 'payment_term', label: '采购账期', format: termLabel },
    { key: 'status', label: '状态 / 隔离待处理', format: receiptStatus },
    C('next_delivery_date', '最近待到货日'), C('payment_due_date', '付款到期日'),
  ],
}
export function createLabel(resource: string) {
  return ({ purchases: buyer() && '新建采购' } as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const fields: Field[] = resource === 'purchases' ? purchaseFields() : []
  const path = endpoint(resource)
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'purchases') {
    a.push('查看明细', '处理记录')
    if (['approved', 'partial', 'received'].includes(r.status)) {
      a.push('质保记录')
      if (buyer() || warehouse()) a.push('登记采购质保', '处理采购质保')
    }
    if (buyer() || money()) a.push('附件')
    if (contractReader()) a.push('预览采购合同')
    if (buyer() && r.status === 'draft') a.push('修改采购', '提交采购')
    if (r.status === 'submitted') {
      if (r.change_request) a.push(r.can_review_change ? '处理修改申请' : '查看修改申请')
      else {
        // 待审批单与草稿一样可整单作废（原因必填）；有待处理修改申请时须先由审批人处理。
        if (buyer()) a.push('申请修改', '作废采购')
        if (purchaseApprover(r)) a.push('批准采购', '退回修改')
      }
    }
    if (warehouse() && ['approved', 'partial'].includes(r.status)) a.push('收货')
    if (buyer() && ['approved', 'partial'].includes(r.status)) a.push('更新到货计划')
    if (warehouse() && r.lines?.some((l: Row) => Number(l.pending_quantity) > 0)) a.push('隔离品合格入库', '隔离品退回供应商')
    if (buyer() && r.status === 'draft') a.push('作废采购')
    if (buyer() && ['approved', 'partial'].includes(r.status)) a.push('取消未收余量', '整单取消未收余量')
  }
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (['申请修改', '处理修改申请', '查看修改申请'].includes(name)) {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    const pending = detail.change_request
    if (name === '申请修改') return {
      title: name, subject: detail.code, path: `${endpoint(resource)}${r.id}/request-change/`,
      submitLabel: '提交修改申请',
      fields: [{ ...reason, label: '修改原因', type: 'textarea', hint: '请写清哪项填错、准备怎样修改，例如第 3 项数量由 10 改为 5。' }],
      blocked: detail.status !== 'submitted' ? '仅待审批采购单可申请修改，请刷新采购单。' : pending ? '已有待处理的修改申请，请勿重复申请。' : undefined,
      notice: { type: 'info', text: '提交申请后暂停本单采购审批。审批人同意后退回草稿，修改完成须重新提交审批。若物料或供应商选错，可直接“作废采购”后重建。已批准订单请按原流程取消余量或更正。' },
      prepare: data => ({ reason: data.reason }),
    }
    const readonly = name === '查看修改申请'
    return {
      title: name, subject: detail.code, path: `${endpoint(resource)}${r.id}/review-change/`, readonly,
      blocked: !pending ? '修改申请已处理，请关闭并刷新采购单。' : !readonly && !detail.can_review_change ? '本人申请不能自行处理，请交由其他有权限的审批人员。' : undefined,
      fields: [
        { key: 'requested_by', label: '申请人', readonly: true, displayOnly: true },
        { key: 'requested_at', label: '申请时间', readonly: true, displayOnly: true },
        { key: 'request_reason', label: '修改原因', type: 'textarea', readonly: true, displayOnly: true },
        ...(!readonly ? [select('decision', '处理结果', [{ value: 'approve', label: '同意，退回草稿修改' }, { value: 'reject', label: '驳回，保留待审批' }]), { ...reason, label: '处理意见', type: 'textarea' as const }] : []),
      ],
      initial: { requested_by: pending?.requested_by, requested_at: dateTimeText(pending?.requested_at, ''), request_reason: pending?.reason },
      prepare: data => ({ request_id: pending?.id, decision: data.decision, reason: data.reason }),
      submitLabel: '确认处理申请',
      notice: { type: 'info', text: '同意：退回草稿，采购修改后重新提交审批。驳回：保留原采购内容，继续待审批。处理记录会保留；管理员处理本人申请须在意见中说明例外原因。' },
    }
  }
  if (name === '整单取消未收余量') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    const remaining = detail.lines.filter((line: Row) => Number(decimalDifference(line.quantity, line.received_quantity, line.cancelled_quantity)) > 0)
    const pending = remaining.filter((line: Row) => Number(line.pending_quantity || 0) > 0)
    const blocked = !['approved', 'partial'].includes(detail.status)
      ? '采购状态已变化，请刷新列表；草稿和待审批采购请用“作废采购”整单作废。'
      : pending.length
        ? `本单有 ${pending.length} 条明细仍在待检，请仓管先完成隔离品合格入库或退回供应商，再整单取消。也可按明细取消其他未收物料。`
        : !remaining.length ? '本单没有可取消的未收余量，请刷新采购单。' : undefined
    return {
      title: name, subject: detail.code || r.code || `采购单 #${r.id}`,
      path: `${endpoint(resource)}${r.id}/cancel-remainder/`,
      submitLabel: '确认整单取消未收余量', fields: [reason], blocked,
      prepare: data => ({ reason: data.reason }),
      alternatives: [{ label: '改为按明细取消', open: () => actionCommand(resource, r, '取消未收余量') }],
      notice: { type: 'warning', text: `将一次取消本 PO 全部 ${remaining.length} 条明细的未收余量，无需逐条填写数量。已收货、库存和付款流水保留，应付按取消金额冲减；提交时以最新未收余量为准。` },
    }
  }
  if (name === '取消未收余量') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    const lines = detail.lines.filter((line: Row) => Number(decimalDifference(line.quantity, line.received_quantity, line.cancelled_quantity)) > 0 && Number(line.pending_quantity || 0) === 0)
    return {
      title: name, path: `${endpoint(resource)}${r.id}/cancel-remainder/`,
      alternatives: [{ label: '改为整单取消未收余量', open: () => actionCommand(resource, r, '整单取消未收余量') }],
      fields: [reason, { ...rows('lines', '本次取消明细', [
        { key: 'line', label: '明细ID', hidden: true },
        { key: 'item_label', label: '采购物料', readonly: true, displayOnly: true },
        { key: 'remaining', label: '可取消未收数量', readonly: true, displayOnly: true },
        { ...qty, label: '本次取消数量', numeric: { scale: 3, min: 0 } },
      ]), readonly: true, compact: true }],
      initial: { lines: lines.map((line: Row) => ({ line: line.id, item_label: `${line.item_name} · ${line.assembly_unit || '未分单元'}`, remaining: decimalDifference(line.quantity, line.received_quantity, line.cancelled_quantity), quantity: '0' })) },
      prepare: data => {
        const selected = data.lines.filter((line: Row) => Number(line.quantity || 0) !== 0)
        if (!selected.length) throw new Error('请至少填写一条本次取消数量。')
        return { reason: data.reason, lines: selected.map((line: Row) => ({ line: line.line, quantity: line.quantity })) }
      },
      ...(lines.length ? {} : { blocked: '没有可取消的未收明细，请先处理隔离中的到货或刷新采购单。' }),
      notice: { type: 'warning', text: '仅取消填写数量的明细，填 0 的行继续履约；应付按本次取消金额冲减。隔离明细需先处理，已收数量不能取消。' },
    }
  }
  if (['质保记录', '登记采购质保', '处理采购质保'].includes(name)) {
    const path = `/business/purchases/${r.id}/warranty/`, info = await read(path)
    if (name === '质保记录') return { title: name, path, readonly: true, initial: { cases: info.cases.map((x: Row) => ({ ...x, within_warranty: x.within_warranty == null ? '' : x.within_warranty ? '是' : '否' })) }, fields: [rows('cases', '质保记录', [t('item', '物料'), { ...t('status', '质保进度'), flow: 'warranty' }, t('id', '编号'), t('date', '报修日期'), t('quantity', '数量'), t('description', '故障'), t('response', '供应商响应与处理'), t('warranty_end', '质保截止'), t('within_warranty', '报修时在保'), t('replacement', '换货收货流水'), t('returned', '退货流水'), t('expense', '费用原单')])] }
    if (name === '登记采购质保') return { title: name, path, fields: [select('receipt', '原收货批次', info.receipts.map((x: Row) => ({ value: x.id, label: `批次${x.id} · ${x.item} · 数量${quantityText(x.quantity)} · 质保至${x.warranty_end}` }))), date('date', '报修日期'), qty, { key: 'description', label: '故障描述', type: 'textarea' }], notice: { type: 'info', text: `逐批按合格收货日起 ${info.warranty_months ?? 12} 个月提示质保。登记不改变库存和成本；退换货复用原库存业务，费用由财务登记后关联。` } }
    // 只取收货和采购退货两类流水，由服务端按类型过滤，不再拉取整个项目的全部库存流水。
    const [receipts, returns] = await Promise.all([
      all('/business/moves/', { project: r.project, kind: 'receipt' }),
      all('/business/moves/', { project: r.project, kind: 'purchase_return' }),
    ])
    const expenses = money() ? await all('/business/entries/', { project: r.project, kind: 'expense', cancelled: false }) : []
    return { title: name, path, fields: [select('case', '质保事项', info.cases.filter((x: Row) => ['待响应', '维修中'].includes(x.status)).map((x: Row) => ({ value: x.id, label: `${x.id} · ${x.item} · ${x.description}` }))), select('status', '处理结果', [{ value: 'repairing', label: '维修中' }, { value: 'replaced', label: '已更换' }, { value: 'closed', label: '已关闭' }]), { key: 'response', label: '供应商响应、责任与处理说明', type: 'textarea' }, select('replacement', '补换货收货流水', receipts.map(x => ({ value: x.id, label: `${x.id} · ${x.item_name} · ${quantityText(x.quantity)}` })), true), select('returned', '原批次退货流水', returns.map(x => ({ value: x.id, label: `${x.id} · ${x.item_name} · ${quantityText(x.quantity)}` })), true), ...(money() ? [select('expense', '关联已登记费用', expenses.map(x => ({ value: x.id, label: `${x.title} · ${formatMoney(x.amount)}` })), true)] : [])], prepare: values => ({ ...values, expected_updated_at: info.cases.find((x: Row) => x.id === Number(values.case))?.updated_at }) }
  }
  if (name === '更新到货计划') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    return { title: name, path: `${endpoint(resource)}${r.id}/delivery-plan/`, fields: [optionalReason(undefined, '选填，如供应商确认的改期原因；不填按「更新到货计划」记录'), { ...rows('lines', '未完成明细', [{ key: 'id', label: '明细ID', hidden: true }, { ...t('item_name', '物料'), readonly: true }, date('due_date', '承诺到货日期')]), readonly: true }], initial: { lines: detail.lines.filter((l: Row) => Number(decimalDifference(l.quantity, l.received_quantity, l.cancelled_quantity)) > 0).map((l: Row) => ({ ...l, due_date: l.due_date || detail.due_date })) }, prepare: data => ({ ...(data.reason ? { reason: data.reason } : {}), expected_updated_at: detail.updated_at, lines: data.lines.map((l: Row) => ({ id: l.id, due_date: l.due_date })) }), notice: { type: 'info', text: '更新供应商承诺到货日期并留记录，不改变原应付期限。' } }
  }
  if (name === '处理记录') return { title: name, path: '', readonly: true, initial: { lines: (await all(`/business/purchases/${r.id}/handling-history/`)).map(l => ({ ...l, date: dateTimeText(l.date), quantity_summary: l.lines.map((row: Row) => `明细${row.line || row.id}：数量 ${row.quantity || '0'}，隔离 ${row.pending_quantity || '0'}${row.remark ? `，备注：${row.remark}` : ''}`).join('；'), operation: ({ 'purchase.request_change': '申请修改', 'purchase.review_change': l.decision === 'approve' ? '同意修改申请' : '驳回修改申请', 'purchase.reject': '退回修改', 'purchase.edit': '修改采购', 'purchase.receive': '到货登记', 'purchase.quality_accept': '隔离品合格入库', 'purchase.quality_return': '隔离品退回供应商', 'purchase.delivery_plan': '更新到货计划' } as Record<string, string>)[l.operation] || l.operation })) }, fields: [rows('lines', '处理记录', [t('date', '时间'), t('actor', '操作人'), t('operation', '操作'), t('reason', '原因 / 处理意见'), t('quantity_summary', '明细与数量'), t('next_step', '后续处理')])] }
  if (name === '修改采购') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    return { title: name, path: `${endpoint(resource)}${r.id}/edit/`, fields: [date('due_date', '交期'), ...termFields(true).map(f => ({ ...f, ...(f.key === 'payment_days' ? { visibleWhen: (d: Row) => (d.payment_term || detail.payment_term) === 'custom' } : {}), label: f.key === 'payment_term' ? '采购账期' : f.label, optional: true, hint: f.key === 'payment_term' ? '草稿阶段可调整；月结＝每批合格收货当月月底＋天数。' : f.hint })), { ...date('payment_due_date', '付款到期日'), optional: true, initial: '', visibleWhen: (d: Row) => (d.payment_term || detail.payment_term) === 'manual', hint: '仅指定日期账期填写；现付/月结由实际收货自动计算。' }, t('note', '说明', true), { key: 'warranty_months', label: '供应商质保月数', numeric: { scale: 0, min: 1, max: 120 } }, reason, overBomReason, { ...rows('lines', '采购明细', [{ key: 'id', label: '明细ID', hidden: true }, { ...t('item_name', '物料'), readonly: true }, { ...qty, numeric: { scale: 3, min: 0.001 } }, price, date('due_date', '明细交期')]), readonly: true, compact: true }], initial: { ...detail, lines: detail.lines.map((l: Row) => ({ ...l, due_date: l.due_date || detail.due_date })) }, prepare: data => ({ due_date: data.due_date, ...((data.payment_term || detail.payment_term) === 'manual' ? { payment_due_date: data.payment_due_date } : {}), ...(data.payment_term ? { payment_term: data.payment_term } : {}), ...(data.payment_days !== undefined && data.payment_days !== '' && data.payment_days !== null ? { payment_days: data.payment_days } : {}), note: data.note, warranty_months: data.warranty_months, reason: data.reason, ...(data.over_bom_reason ? { over_bom_reason: data.over_bom_reason } : {}), expected_updated_at: detail.updated_at, lines: data.lines.map((l: Row) => ({ id: l.id, quantity: l.quantity, unit_price: l.unit_price, due_date: l.due_date })) }) }
  }
  if (name === '批准采购') {
    const check = await read(`/business/purchases/${r.id}/budget-check/`)
    const summary = check.scope === 'purchasing'
      ? `本单 ¥${formatMoney(check.purchase_amount)}；材料占用 ¥${formatMoney(check.materials_occupied)}；累计采购净额 ¥${formatMoney(check.purchase_net)}${check.configured ? `；材料预算 ¥${formatMoney(check.materials_budget)}` : ''}。`
      : `本单 ¥${formatMoney(check.purchase_amount)}；批准后实际＋在途 ¥${formatMoney(check.occupied_total)}；累计采购净额 ¥${formatMoney(check.purchase_net)}。`
    const bomWarnings: string[] = check.bom_warnings || []
    const bomText = bomWarnings.length ? `BOM 核对：${bomWarnings.join('；')}。` : ''
    const content = approvalContent(r, check)
    if (check.over_budget) return {
      title: '超预算采购审批', path: `/business/purchases/${r.id}/approve-over-budget/`,
      notice: { type: 'warning', text: `${check.warnings.join('；')}。${summary}${bomText}` },
      fields: [...content.fields, { ...reason, label: '超预算批准原因', type: 'textarea' }, { key: 'confirmed', label: '确认承担本次超预算采购', type: 'boolean', initial: false }],
      initial: content.initial,
      prepare: data => ({ reason: data.reason, confirmed: data.confirmed, expected_snapshot: check.snapshot }),
    }
    return {
      title: name, path: `/business/purchases/${r.id}/approve/`, fields: [...content.fields, { ...reason, optional: true, hint: '申请人不可自行审批；管理员例外处理本人申请时必填。' }],
      initial: content.initial,
      prepare: data => (data.reason ? { reason: data.reason } : {}),
      notice: { type: check.configured && !bomWarnings.length ? 'info' : 'warning', text: `${check.configured ? `预算检查通过。${summary}` : `项目未设置预算，本次批准不进行预算拦截。${summary}`}${bomText}` },
    }
  }
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  let receive: Command['prepare']
  const routes: Record<string, string> = {
    提交采购: 'submit',
    批准采购: 'approve',
    收货: 'receive',
    取消未收余量: 'cancel-remainder',
    作废采购: 'cancel-remainder',
    退回修改: 'reject',
    隔离品合格入库: 'quality-accept',
    隔离品退回供应商: 'quality-return',
  }
  if (routes[name]) path += routes[name] + '/'
  if (['提交采购', '批准采购'].includes(name)) fields = []
  if (name === '退回修改') {
    const content = approvalContent(r, {})
    fields = [...content.fields, reason]
    initial = content.initial
  }
  if (['查看明细', '收货', '隔离品合格入库', '隔离品退回供应商'].includes(name)) {
    const detail = await read(endpoint(resource) + r.id + '/')
    readonly = name === '查看明细'
    if (readonly) {
      const lines = (detail.lines || []).map((line: Row) => purchaseDetailLine(line, detail))
      const has = (key: string) => lines.some((line: Row) => Number(line[key] || 0) > 0)
      const latest = lines.map((line: Row) => line.last_received_date).filter(Boolean).sort().pop() || ''
      fields = [
        { key: 'supplier_name', label: '供应商' },
        { key: 'project_label', label: '项目' },
        { key: 'receipt_status', label: '到货与检验状态' },
        { key: 'last_received_label', label: '最近入库日期' },
        { key: 'due_date', label: '交期' },
        ...(money() || buyer() ? [{ key: 'total_label', label: '含税合计（元）' }] : []),
        { key: 'payment_term_label', label: '采购账期' },
        { key: 'payment_due_date', label: '付款到期日', optional: true },
        { key: 'warranty_months', label: '供应商质保月数' },
        { key: 'note', label: '说明', optional: true, wide: true },
        // 明细首列合并名称、编码、规格（窄面板不用横向找编码）；入库日期列出最近一批，分批到货逐批列出。
        rows('lines', '采购明细', [
          // 列宽按 1366 宽屏的明细工作区（约 1010px）收紧，入库日期列不用横向滚动就能看到。
          { key: 'material_text', label: '物料 / 编码 / 规格', multiline: true, width: 192 },
          { key: 'project_unit', label: '项目号 / 单元', multiline: true, width: 110 },
          { ...t('due_date', '明细交期'), width: 116, short: true },
          { ...qty, label: '采购数量', width: 80, short: true },
          ...(money() || buyer() ? [{ ...price, width: 100, short: true }] : []),
          { ...t('received_quantity', '已收'), width: 64, short: true },
          { ...t('remaining', '待收'), width: 64, short: true },
          { ...t('cancelled_quantity', '已取消'), width: 72, short: true },
          ...(has('returned_quantity') ? [{ ...t('returned_quantity', '已退货'), width: 64, short: true }] : []),
          ...(has('pending_quantity') ? [{ ...t('pending_quantity', '隔离待处理'), width: 88, short: true }] : []),
          { key: 'received_label', label: '入库日期', multiline: true, width: 136 },
        ]),
      ]
      initial = { ...detail, receipt_status: receiptStatus(detail), last_received_label: latest, payment_term_label: termLabel(detail), project_label: [detail.project_code, detail.project_name].filter(Boolean).join(' · '), total_label: purchaseTotal(detail.lines || []), lines: lines.map((line: Row) => ({ ...line, ...Object.fromEntries(['quantity', 'received_quantity', 'cancelled_quantity', 'returned_quantity', 'pending_quantity', 'remaining'].filter(key => key in line).map(key => [key, quantityText(line[key])])), ...(line.unit_price == null || line.unit_price === '' ? {} : { unit_price: formatMoney(line.unit_price) }) })) }
    } else {
      const locations: string[] = name === '隔离品退回供应商' ? [] : await read('/business/stocks/locations/')
      // The API renders timestamps in the business timezone; preserve that date across browser timezones.
      const createdDate = String(detail.created_at || '').slice(0, 10)
      // 入库日期放在第一项：保存后写入库存流水，在库存流水、现有库存和采购明细中都能查到。
      fields = [
        ...(name === '隔离品退回供应商' ? [] : [
          { ...date('received_date', name === '收货' ? '入库日期（实际到货 / 合格收货日）' : '入库日期（检验合格日）'), hint: name === '收货' ? '按实际到货当天填写，记入库存流水，可在「库存流水」「现有库存」和采购明细中查到；仅隔离的到货也按实际日期登记。早于采购创建日期须填补录原因，锁账期间不能补录。' : '按检验合格当天填写，记入库存流水；不能早于该明细的隔离到货日期。早于采购创建日期须填补录原因，锁账期间不能补录。' },
          { key: 'location', label: '库位', initial: '主仓', suggestions: locations, hint: '从已有库位中选择；全角字符和多余空格会自动统一。' },
          { key: 'new_location', label: '新建库位', type: 'boolean' as const, initial: false, optional: true, hint: '仅首次使用某个库位时勾选，避免同一库位录成多种写法。' },
          { key: 'backfill_reason', label: '补录原因', type: 'textarea' as const, optional: !createdDate, visibleWhen: (data: Row) => !createdDate || (!!data.received_date && data.received_date < createdDate), hint: `采购创建日期${createdDate ? `为 ${createdDate}` : '以前'}，请说明实际到货依据与迟录原因；补录保留审计。` },
        ]),
        name === '隔离品退回供应商' ? reason : optionalReason(name === '收货' ? '送货单号 / 备注' : undefined, `选填，如送货单号、检验记录；不填按「${name === '收货' ? '采购收货' : '隔离品合格入库'}」记录`),
        { ...rows('lines', '本次收货', [
          { key: 'line', label: '明细ID', hidden: true },
          { key: 'item_label', label: '采购物料', readonly: true, displayOnly: true },
          qty,
          ...(name === '收货' ? [{ key: 'pending_quantity', label: '不合格隔离数量', initial: '0' }] : []),
        ]), readonly: true, compact: true },
      ]
      initial = {
        lines: detail.lines
          .map((l: Row) => ({
            line: l.id,
            item_label: `${l.item_name} · ${l.assembly_unit || '未分单元'}`,
            quantity: name === '收货' ? decimalDifference(l.quantity, l.received_quantity, l.cancelled_quantity, l.pending_quantity || '0') : l.pending_quantity,
            ...(name === '收货' ? { pending_quantity: '0' } : {}),
          }))
          .filter((l: Row) => Number(l.quantity) > 0),
      }
      if (name === '收货') {
        // 默认全部勾选并按待收填入（一键整单收货不变）；未到货的行取消勾选即可。
        const cancel = buyer()
        const lines = detail.lines.map((line: Row) => ({
          ...materialDetails(line), line: line.id, project_code: detail.project_code,
          required_quantity: line.bom_quantity ?? line.quantity,
          remaining: decimalDifference(line.quantity, line.received_quantity, line.cancelled_quantity, line.pending_quantity || '0'),
          quantity: decimalDifference(line.quantity, line.received_quantity, line.cancelled_quantity, line.pending_quantity || '0'),
          quarantined: line.pending_quantity || '0',
          selected: true, ...(cancel ? { cancel_remainder: false } : {}),
          pending_quantity: '0', remark: '',
        })).filter((line: Row) => Number(line.remaining) > 0)
        fields[fields.length - 1] = warehouseLines('receipt', lines, { cancel })
        // 「余量不再到货」与「取消未收余量」同一规则：原因必填，应付按取消金额冲减，需采购权限。
        if (cancel) fields.push({
          key: 'cancel_reason', label: '余量不再到货原因', type: 'textarea',
          visibleWhen: (data: Row) => (data.lines || []).some((line: Row) => line.selected !== false && line.cancel_remainder === true),
          placeholder: '如 供应商停产不再补货、改用库存、设计变更不再需要',
          hint: '勾选「余量不再到货」的行将同时取消剩余未收数量，应付按取消金额冲减，与「取消未收余量」相同并保留记录。',
        })
        initial = { lines }
        const limits = Object.fromEntries(lines.map((line: Row) => [String(line.line), String(line.remaining)]))
        receive = data => receiptLines(data, limits)
      }
    }
  }
  let prepare: Command['prepare']
  if (['收货', '隔离品合格入库', '隔离品退回供应商'].includes(name)) prepare = receive || receiptLines
  const notice: Command['notice'] = name === '作废采购'
    ? { type: 'warning', text: `将作废本单全部采购明细，请填写作废原因。${r.status === 'submitted' ? '待审批单作废后审批人无需再处理。' : ''}` }
    : name === '提交采购'
      ? { type: 'info', text: `${[r.supplier_name, r.project_code || r.project_name].filter(Boolean).join(' · ')} · ${(r.lines || []).length} 行明细 · 含税合计 ${purchaseTotal(r.lines || [])} 元。提交后由项目经理、采购经理或管理员审批，申请人不能审批本人提交的采购。` }
      : undefined
  const successNote: Command['successNote'] = name === '收货' ? result => (result.cancelled?.length ? `已同时取消 ${result.cancelled.length} 行未收余量，应付已按取消金额冲减。` : '') : undefined
  return { title: name, path, fields, initial, method, readonly, ...(prepare ? { prepare } : {}), ...(notice ? { notice } : {}), ...(successNote ? { successNote } : {}) }
}
// 采购详情明细：首列合并名称、编码、规格（及图号、品牌），项目号与单元一列；入库日期取逐批合格入库记录。
export function purchaseDetailLine(line: Row, detail: Row): Row {
  const receipts: Row[] = line.receipts || []
  const remaining = decimalDifference(line.quantity || '0', line.received_quantity || '0', line.cancelled_quantity || '0', line.pending_quantity || '0')
  const drawing = line.drawing_number ? `图号 ${line.drawing_number}${line.drawing_revision ? `（${line.drawing_revision}）` : ''}` : ''
  return {
    ...line,
    material_text: [
      line.item_name || '—',
      [line.item_code && `编码 ${line.item_code}`, line.specification && `规格 ${line.specification}`].filter(Boolean).join(' · '),
      [drawing, line.brand && `品牌 ${line.brand}`].filter(Boolean).join(' · '),
    ].filter(Boolean).join('\n'),
    project_unit: [detail.project_code || '—', line.assembly_unit || '未分单元'].join('\n'),
    remaining: remaining.startsWith('-') ? '0' : remaining,
    // 首行是最近入库日期；分批到货时逐批列出日期和数量，批次多时只列最近 3 批，单元格不被撑得过高。
    received_label: !receipts.length ? '—' : receipts.length === 1 ? receipts[0]!.received_date : [
      line.last_received_date || receipts[receipts.length - 1]!.received_date,
      `共 ${receipts.length} 批${receipts.length > 3 ? '，列出最近 3 批' : ''}`,
      ...receipts.slice(-3).map(receipt => `${receipt.received_date} 入库 ${quantityText(receipt.quantity)}`),
    ].join('\n'),
  }
}
// 审批、退回前不离开对话框就能核对的采购内容：供应商、项目、交期、账期、合计和逐行明细（含 BOM 核对结果）。
// 只用列表行已有的数据，不额外读取明细；明细按“一行一条”的只读文本列出，侧栏和窄屏里也不会撑成逐行表单。
export function approvalContent(r: Row, check: Row): { fields: Field[]; initial: Row } {
  const shown = (key: string, label: string, extra: Partial<Field> = {}): Field => ({ key, label, readonly: true, displayOnly: true, ...extra })
  const notes: Record<string, string> = check.bom_lines || {}
  const lines = (r.lines || []).map((line: Row, i: number) => [
    `${i + 1}. ${[line.item_code, line.item_name, line.specification].filter(Boolean).join(' · ')}`,
    ...(line.assembly_unit ? [line.assembly_unit] : []),
    `${quantityText(line.quantity)}${line.unit ? ` ${line.unit}` : ''} × ${purchaseTotal([{ quantity: '1', unit_price: line.unit_price }])} = ${purchaseTotal([line])}`,
    line.bom_line ? '按 BOM 下单' : notes[String(line.id)] || '未关联 BOM 行',
  ].join('｜'))
  return {
    fields: [
      shown('supplier_name', '供应商'),
      shown('project_label', '项目'),
      shown('schedule_label', '交期 · 采购账期'),
      shown('total_label', '含税合计（元）'),
      ...(check.over_bom_reason ? [shown('over_bom_reason', '超 BOM 采购原因', { wide: true })] : []),
      shown('approval_lines', `采购明细（${lines.length} 行）`, { type: 'textarea', wide: true }),
    ],
    initial: {
      supplier_name: r.supplier_name || '—',
      project_label: [r.project_code, r.project_name].filter(Boolean).join(' · ') || '—',
      schedule_label: `${r.due_date || '—'} · ${termLabel(r)}`,
      total_label: purchaseTotal(r.lines || []),
      over_bom_reason: check.over_bom_reason || '',
      approval_lines: lines.join('\n') || '—',
    },
  }
}
// 未勾选或未到货的明细（合格与隔离数量均为 0）本次不提交，勾选了「余量不再到货」的行即使本次为 0 也提交；
// 全部为 0 时在前端直接提示。limits 为各明细待收数量：多送在前端先拦下，服务端锁内仍会重新校验。
export function receiptLines(data: Row, limits?: Record<string, string>): Row {
  const all: Row[] = data.lines || []
  if (limits && !all.some(l => l.selected !== false)) throw new Error('请至少勾选一条本次到货的明细。')
  const lines: Row[] = []
  all.forEach(({ selected, cancel_remainder: cancel, ...line }, index) => {
    if (selected === false) return
    if (Number(line.quantity || 0) === 0 && Number(line.pending_quantity || 0) === 0 && cancel !== true) return
    const limit = limits?.[String(line.line)]
    if (limit != null && decimalDifference(limit, String(line.quantity || '0'), String(line.pending_quantity || '0')).startsWith('-')) {
      throw new Error(`第 ${index + 1} 行超过待收 ${quantityText(limit)}：多送部分不能入本单，请联系采购「新建采购」补单后再收。`)
    }
    lines.push(cancel === true ? { ...line, cancel_remainder: true } : line)
  })
  if (!lines.length) throw new Error('请至少填写一条到货数量。')
  return { ...data, lines }
}
