import { all, download, read } from '../api'
import { catalog, options } from '../catalog'
import { can } from '../session'
import type { Column, Command, Row } from '../types'
import { C, date, finance, reason, t } from './shared'
import { termLabel } from './payment-terms'

const kinds: Record<string, string> = { settlement: '业务对账', prepayment: '预付款核准', refund: '退款对账' }
const states: Record<string, string> = { draft: '待确认', confirmed: '已确认', void: '已作废' }
export const columns: Record<string, Column[]> = {
  reconciliations: [C('code', '对账单号'), C('project_name', '项目'), C('entry_title', '款项'),
    { key: 'kind', label: '类型', format: r => kinds[String(r.kind)] || String(r.kind) },
    { key: 'status', label: '状态', format: r => r.status !== 'void' && !r.valid ? '原业务已变化' : states[String(r.status)] || String(r.status) },
    C('difference', '对账差异'), C('approved_amount', '核准金额'), C('remaining_amount', '剩余额度'), C('confirmed_name', '确认人')],
  'bank-records': [C('date', '银行日期'), C('account', '账户'), C('reference', '流水号 / 导入标识'), C('counterparty', '对方户名'), C('project_name', '项目'), C('amount', '收入 / 支出'), C('remaining_amount', '未匹配金额'),
    { key: 'void_reason', label: '状态', format: r => r.void_reason ? '已作废' : r.needs_review ? '待核实户名' : Number(r.remaining_amount) === 0 ? '已核对' : '待认领 / 匹配' }],
}
export const createLabel = (resource: string) => resource === 'bank-records' && finance() ? '登记银行到账 / 出账' : ''
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const c = await catalog(['projects'])
  return { title: String(createLabel(resource)), path: '/business/bank-records/', fields: [
    date(), t('account', '账户标识'), t('reference', '银行流水号'), t('counterparty', '对方户名'),
    t('amount', '银行金额（收入正数、支出负数）'),
    { key: 'project', label: '已知项目（不确定可留空）', type: 'select', optional: true, options: options(c.projects) }, reason,
  ], initial: projectId ? { project: projectId } : {}, notice: { type: 'info', text: '按银行实际记录登记，不直接改变项目余额。已登记过收付款的请选择匹配；尚未登记的收入请选择认领，避免重复收款。未知项目的记录保留在全局待认领列表。' } }
}
export async function reconciliationCommand(entry: Row, prepayment = false): Promise<Command> {
  const docs = (await all('/business/documents/', { project: entry.project })).filter(d => d.sale || d.purchase || ['contract', 'receipt'].includes(d.category))
  const kind = prepayment ? 'prepayment' : Number(entry.balance) < 0 ? 'refund' : 'settlement'
  return { title: prepayment ? '申请预付款核准' : '生成对账单', path: '/business/reconciliations/',
    fields: [t('counterparty_balance', '对方确认余额（待退款填负数）'), t('approved_amount', '本次申请额度（元）'),
      { key: 'basis', label: '合同编号及付款条款依据', optional: !prepayment },
      { key: 'document', label: '对账或合同附件（先在原单或项目上传）', type: 'select', optional: true, options: docs.map(d => ({ value: d.id, label: d.original_name })) }, reason],
    initial: { counterparty_balance: String(entry.balance), approved_amount: String(Math.abs(Number(entry.balance))) },
    prepare: data => ({ ...data, entry: entry.id, kind }), notice: { type: 'info', text: prepayment ? '预付款必须填写合同依据，由项目经理或管理员核准。未收货部分不能通过普通对账付款。' : '保存原业务快照供核对。普通采购付款额度受已收货净额约束；差异须回到原业务纠正。生成后仍需财务确认。' } }
}
export function actionNames(resource: string, r: Row): string[] {
  if (resource === 'reconciliations') return ['查看对账明细',
    ...(r.status === 'draft' && r.valid && (r.kind === 'prepayment' ? can(['admin', 'manager']) : finance()) ? ['确认对账'] : []),
    ...(r.status !== 'void' && finance() ? ['作废对账'] : [])]
  if (!finance()) return []
  return ['查看银行明细', ...(!r.void_reason ? [
    ...(r.needs_review ? ['核实对方户名'] : []),
    ...(!r.needs_review && Number(r.remaining_amount) > 0 ? [...(Number(r.amount) > 0 ? ['认领到账', '关联未认领款退回'] : []), '匹配已有收付款'] : []),
    ...(Number(r.amount) > 0 && (r.returns || []).some((m: Row) => !m.reversal_of && !m.reversal__id) ? ['撤销退回关联'] : []),
    ...(r.matches.some((m: Row) => !m.reversal_of && !m.reversal__id) ? ['撤销银行匹配'] : []),
    ...(Number(r.remaining_amount) === Math.abs(Number(r.amount)) ? ['作废误录银行记录'] : []),
  ] : [])]
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '查看银行明细' && r.source?.file) {
    const command = await actionCommand(resource, { ...r, source: undefined }, name)
    command.fields.unshift({ key: 'sourceFacts', label: '原始银行凭据', type: 'rows', fields: [t('label', '字段'), t('value', '内容')] })
    command.initial = { ...command.initial, sourceFacts: Object.entries({ 文件: r.source.file, 原文件行号: r.source.row, 银行原始编号: r.source.original_reference, 原始户名: r.source.counterparty || '原文件未提供', 对方账号: r.source.counterparty_account, 交易时间: r.source.timestamp, 银行余额: r.source.balance }).map(([label, value]) => ({ label, value })) }
    return command
  }
  if (name === '确认对账' || name === '作废对账') return { title: name, path: `/business/reconciliations/${r.id}/${name === '确认对账' ? 'confirm' : 'void'}/`, fields: [reason], notice: { type: 'info', text: name === '确认对账' ? '确认前请查看对账明细并核对对方余额、合同、收退货及原收付款。服务端将重新检查源数据和额度。' : '保留原对账及已关联流水，未使用额度立即失效。' } }
  if (name === '查看对账明细') {
    const d = await read(`/business/reconciliations/${r.id}/`), s = d.snapshot
    const facts = [
      ['项目', s.project.name], ['款项', s.entry.title], ['原金额', s.entry.amount], ['冲减', s.entry.credit_amount],
      ['原已结算', s.paid], ['系统余额', s.balance], ['对方余额', d.counterparty_balance], ['差异', d.difference],
      ['当时可结算额度', s.eligible], ['申请额度', d.approved_amount], ['剩余额度', d.remaining_amount], ['合同依据', d.basis],
      ['确认人', d.confirmed_name], ['确认时间', d.confirmed_at || ''], ['作废原因', d.void_reason],
      ...(s.monthly ? [['对账月份', s.monthly.month], ['月期初', s.monthly.opening], ['月收货', s.monthly.received], ['月退货', s.monthly.returned], ['月净付款', s.monthly.paid], ['月期末', s.monthly.closing]] : []),
      ...(s.purchase ? [['采购单', s.purchase.code], ['供应商', s.purchase.supplier], ['采购账期', termLabel(s.purchase)], ['收货净额', s.received_net]] : []),
      ...(s.contract ? [['合同编号', s.contract.contract_number || ''], ['现行合同金额', s.contract.amount]] : []),
    ].map(([label, value]) => ({ label, value }))
    return { title: name, path: '', readonly: true, initial: { facts, lines: s.lines || [], payments: s.payments, deliveries: s.deliveries || [] },
      fields: [
        { key: 'facts', label: '对账依据与差异', type: 'rows', fields: [t('label', '项目'), t('value', '内容')] },
        { key: 'lines', label: '采购明细快照', type: 'rows', fields: [t('item__name', '物料'), t('quantity', '采购数量'), t('unit_price', '单价'), t('received_quantity', '已收'), t('returned_quantity', '已退'), t('cancelled_quantity', '取消'), t('pending_quantity', '隔离')] },
        { key: 'payments', label: '原资金流水', type: 'rows', fields: [t('id', '流水ID'), t('amount', '金额'), t('reversal_of', '冲销原记录')] },
        { key: 'deliveries', label: '交付快照', type: 'rows', fields: [t('code', '批次'), t('quantity', '数量'), t('accepted_date', '验收日期')] },
      ], notice: { type: d.valid ? 'info' : 'warning', text: d.valid ? '以下为生成时的原业务快照。确认后的分次收付消耗额度；其他业务变化需重新核对。' : '原业务已变化或此对账单已作废，不能用于新的付款。' },
      actions: d.document ? [{ label: '下载对账附件', run: async () => { const doc = await read(`/business/documents/${d.document}/`); await download(doc.download_url, doc.original_name) } }] : [] }
  }
  const path = `/business/bank-records/${r.id}/`
  if (name === '核实对方户名') return { title: name, path: path + 'review/', fields: [t('counterparty', '核实后的对方户名'), reason], notice: { type: 'info', text: '根据银行回单核实真实户名并填写依据。原始文件内容仍保留在银行明细，核实操作记录审计日志，不自动核销。' } }
  if (name === '关联未认领款退回') {
    const banks = await all('/business/bank-records/')
    return { title: name, path: path + 'return-unclaimed/', fields: [{ key: 'returned', label: '实际退回的银行支出', type: 'select', options: banks.filter(b => !b.void_reason && Number(b.amount) < 0 && Number(b.remaining_amount) > 0 && b.account === r.account && b.counterparty === r.counterparty).map(b => ({ value: b.id, label: `${b.reference} · ${b.date} · 可匹配 ${b.remaining_amount}` })) }, t('amount', '退回金额（元）'), reason], initial: { amount: r.remaining_amount }, notice: { type: 'info', text: '用于错汇、多汇的未认领部分。先登记真实银行支出，再关联原收入；不会虚增合同、费用或项目收付款。' } }
  }
  if (name === '撤销退回关联') return { title: name, path: path + 'reverse-return/', fields: [{ key: 'offset', label: '原退回关联', type: 'select', options: r.returns.filter((m: Row) => !m.reversal_of && !m.reversal__id).map((m: Row) => ({ value: m.id, label: `${m.id} · 银行支出 ${m.returned_id} · ${m.amount}` })) }, reason] }
  if (name === '查看银行明细') return { title: name, path: '', readonly: true, initial: { ...r, lines: r.matches }, fields: [t('reference', '银行流水号'), t('counterparty', '对方户名'), t('amount', '银行金额'), t('remaining_amount', '未匹配金额'), t('reason', '说明'), t('void_reason', '作废原因'), { key: 'lines', label: '匹配与撤销历史', type: 'rows', fields: [t('id', '记录ID'), t('payment_id', '收付流水ID'), t('payment__entry__title', '款项'), t('amount', '匹配金额'), t('reason', '原因'), t('reversal_of', '撤销原匹配')] }, { key: 'returns', label: '未认领款退回历史', type: 'rows', fields: [t('id', '记录ID'), t('source_id', '原收入ID'), t('returned_id', '退回支出ID'), t('amount', '退回金额'), t('reason', '原因'), t('reversal_of', '撤销原关联')] }] }
  if (name === '作废误录银行记录') return { title: name, path: path + 'void/', fields: [reason] }
  if (name === '撤销银行匹配') return { title: name, path: path + 'unmatch/', fields: [{ key: 'match', label: '原匹配', type: 'select', options: r.matches.filter((m: Row) => !m.reversal_of && !m.reversal__id).map((m: Row) => ({ value: m.id, label: `流水 ${m.payment_id} · ${m.amount}` })) }, reason], notice: { type: 'info', text: '仅撤销银行匹配并保留历史，不冲销原收付款。纠正认领错误时，撤销后还需在收付流水冲销原记录，再重新认领。' } }
  if (name === '匹配已有收付款') {
    const payments = await all('/business/payments/', r.project ? { entry__project: r.project } : {})
    return { title: name, path: path + 'match/', fields: [{ key: 'payment', label: '已有收付款流水', type: 'select', options: payments.filter(p => !p.reversal_of && !p.reversed_by && !p.bank_matched && p.method === 'bank' && p.account === r.account && Number(p.cash_amount) * Number(r.amount) > 0 && Math.abs(Number(p.amount)) <= Number(r.remaining_amount)).map(p => ({ value: p.id, label: `${p.id} · ${p.entry_title} · ${p.amount} · ${p.date}` })) }, reason], notice: { type: 'info', text: '按账户、方向和金额核对已有记录，匹配不会新增收付款。若列表为空，请检查原记录的银行方式和账户。' } }
  }
  const entries = await all('/business/entries/', r.project ? { project: r.project } : {})
  const statements = await all('/business/reconciliations/', { status: 'confirmed', kind: 'refund' })
  return { title: name, path: path + 'allocate/', fields: [
    { key: 'entry', label: '认领款项', type: 'select', options: entries.filter(e => e.kind === 'receivable' ? Number(e.balance) > 0 : Number(e.balance) < 0).map(e => ({ value: e.id, label: `${e.project_name} · ${e.title} · 待结 ${e.balance}` })) },
    t('amount', '认领金额（元）'), { key: 'reconciliation', label: '供应商退款对账（客户收款可不选）', type: 'select', optional: true, options: statements.filter(s => s.valid && Number(s.remaining_amount) > 0).map(s => ({ value: s.id, label: `${s.code} · ${s.entry_title} · ${s.remaining_amount}` })) }, reason,
  ], initial: { amount: r.remaining_amount }, notice: { type: 'info', text: '认领会登记收款并匹配本条银行记录。已经登记的款项请使用“匹配已有收付款”，避免重复入账。供应商退款仍需有效退款对账。' } }
}
