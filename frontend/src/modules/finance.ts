import { previewAction } from '../document-preview'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { date } from './shared'
import { reason } from './shared'
import { optionalReason } from './shared'
import { projectLink } from './shared'
import { purchaseLink } from './shared'
import { money as formatMoney } from '../utils/money'
import { fromScaled, MONEY_SCALE, toScaled } from '../utils/decimal'
import { dateTimeText } from '../utils/datetime'
import { finance } from './shared'
import { C } from './shared'
import { project } from './shared'
import { endpoint } from './shared'
import { ledgerStatus } from './shared'
import { all, download, read } from '../api'
import { reconciliationCommand } from './settlement'

// 按绝对值取「分」：待退款余额为负，登记和对账额度都填正数；无法解析时按 0。
function cents(value: unknown): bigint {
  const scaled = toScaled(value, MONEY_SCALE) ?? 0n
  return scaled < 0n ? -scaled : scaled
}
const amount = (value: bigint) => fromScaled(value, MONEY_SCALE)
function cappedAmount(balance: unknown, allowance: unknown): string {
  const remaining = cents(balance), available = cents(allowance)
  return amount(remaining < available ? remaining : available)
}
async function entryReconciliationCommand(entry: Row, prepayment = false): Promise<Command> {
  const command = await reconciliationCommand(entry, prepayment)
  if (entry.purchase && !prepayment && !String(entry.balance).startsWith('-')) {
    const detail = Array.isArray(entry.payment_schedule) ? entry : await read(`/business/entries/${entry.id}/`)
    // The schedule includes all outstanding qualified receipts, including future maturities.
    const eligible = (detail.payment_schedule || []).reduce((total: bigint, row: Row) => total + cents(row.amount), 0n)
    command.initial = { ...command.initial, approved_amount: eligible > 0n ? cappedAmount(entry.balance, amount(eligible)) : '' }
    command.fields = command.fields.map(field => field.key === 'approved_amount'
      ? { ...field, hint: `当前普通结算可申请 ${formatMoney(amount(eligible))} 元；未收货部分请申请预付款核准。保存和确认时都会重新校验。` }
      : field)
  }
  return command
}
export const columns: Record<string, Column[]> = {
  // 类型、项目、当前到期金额、已结算由列表合并为副行；原金额与冲减都在「查看收付流水」里，
  // 约定付款日单独展示；实际到期金额仍只来自已收货批次。
  entries: [
    C('title', '款项'), C('kind', '类型'),
    C('partner_name', '往来单位'), C('project_name', '项目'),
    C('agreed_payment_date', '约定付款日'), C('due_date', '到期日'), C('due_amount', '当前到期金额'),
    C('balance', '待结算'), C('paid_amount', '已结算'),
    { key: 'purchase_code', label: '来源采购单', format: row => row.purchase_code || '—', link: purchaseLink },
    {
      key: 'status',
      label: '状态',
      format: row => {
        const label = (({ cancelled: '已取消', closed: '已结清', refund: '待退款', overdue: '已逾期' } as Record<string, string>)[String(row.status)] || '未结')
        return row.prepaid_excess ? `${label} · 含预付 ${row.prepaid_excess}` : label
      },
      tip: row => row.prepaid_excess
        ? `已付超过合格收货净额 ${formatMoney(row.prepaid_excess)} 元，视为预付；待后续到货或取消余量后再结算。`
        : undefined,
    },
  ],
  // 流水按资金方向显示「收 / 付」，并列出项目与往来单位；对账单显示编号可跳转。
  payments: [
    C('entry_title', '款项'),
    { key: 'amount', label: '收 / 付金额', format: row => row.cash_amount == null ? formatMoney(row.amount) : `${String(row.cash_amount).startsWith('-') ? '付' : '收'} ${formatMoney(String(row.cash_amount).replace(/^-/, ''))}` },
    C('date', '日期'),
    { key: 'project_name', label: '项目', format: row => [row.project_code, row.project_name].filter(Boolean).join(' · ') || '—', link: projectLink },
    { key: 'partner_name', label: '往来单位', format: row => row.partner_name || '—' },
    C('reason', '说明'),
    C('method', '结算方式'), C('account', '账户标识'), C('reference', '银行流水号'),
    C('reversal_of', '冲销原记录'),
    { key: 'reconciliation_code', label: '对账单', format: row => row.reconciliation_code || '—', link: row => row.reconciliation ? { path: '/finance', query: { section: 'reconciliations', resource: 'reconciliations', focus: String(row.reconciliation) } } : undefined },
    { key: 'bank_matched', label: '银行核对', format: r => r.bank_matched ? '已匹配' : '未匹配' },
    { key: 'reversed_by', label: '记录状态', format: ledgerStatus },
  ],
}
export function createLabel(resource: string) {
  return ({ entries: finance() && '登记费用' } as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'entries') {
    path += 'expense/'
    fields = [
      project(),
      t('title', '费用名称'),
      t('amount', '金额（元）'),
      date('due_date', '付款到期日'),
    ]
  }
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'entries') a.push('查看收付流水', '查看到期明细')
  if (resource === 'payments' && r.document) a.push('预览凭证', '下载凭证')
  if (resource === 'payments') a.push('查看凭证')
  if (resource === 'payments' && finance()) a.push('补录凭证')
  if (resource === 'entries' && finance()) {
    if (Number(r.balance) !== 0) a.push('生成对账单')
    if (r.purchase && Number(r.balance) > 0) a.push('申请预付款核准')
    if (Number(r.balance) > 0) a.push('登记收付款')
    if (Number(r.balance) < 0) a.push('退款')
    if (r.kind === 'receivable' && !r.cancelled && Number(r.balance) > 0) a.push('调整到期日')
    if (r.kind === 'expense' && !r.cancelled) a.push('取消费用')
  }
  if (resource === 'payments' && finance() && !r.reversal_of && !r.reversed_by) a.push('冲销付款')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '查看到期明细') return { title: name, path: '', readonly: true, initial: { agreed_payment_date: r.agreed_payment_date, lines: r.payment_schedule || [] }, fields: [...(r.agreed_payment_date ? [t('agreed_payment_date', '约定付款日')] : []), { key: 'lines', label: '未结到期明细', type: 'rows', fields: [t('due_date', '到期日'), t('amount', '待付金额')] }], notice: { type: 'info', text: '约定付款日是指定日期账期的合同约定，仅有日期不产生可付款额度。月结按合格收货当月月底加账期天数，跨月分别到期；指定日期账期只对已合格收货部分到期。已付款优先抵扣先到期部分，退货冲减原收货批次。未收货部分不计入到期，预付款仍需合同核准。' } }
  if (name === '生成对账单' || name === '申请预付款核准') return entryReconciliationCommand(r, name === '申请预付款核准')
  if (name === '补录凭证') {
    const docs = await all('/business/documents/', { project: r.project, category: 'receipt' })
    return { title: name, path: `/business/payments/${r.id}/attach-evidence/`, fields: [{ key: 'document', label: '凭证', type: 'select', upload: { context: { project: r.project }, category: 'receipt' }, options: docs.map(d => ({ value: d.id, label: d.original_name })) }, optionalReason(undefined, '选填；不填按「补充收付凭证」记录')], notice: { type: 'info', text: '追加凭证并留痕，不覆盖原付款金额和历史凭证。' } }
  }
  if (name === '查看凭证') {
    const detail = await read(`/business/payments/${r.id}/`)
    return { title: name, path: '', readonly: true, initial: { lines: detail.evidence.map((d: Row) => ({ ...d, date: dateTimeText(d.date, '') })) }, fields: [{ key: 'lines', label: '凭证记录', type: 'rows', fields: [t('name', '文件'), t('reason', '说明'), t('actor', '补录人'), t('date', '补录时间')] }], actions: detail.evidence.flatMap((d: Row) => [previewAction(d.document, d.name), { label: `下载 ${d.name}`, run: async () => { const doc = await read(`/business/documents/${d.document}/`); await download(doc.download_url, doc.original_name) } }]) }
  }
  if (name === '查看收付流水') return { title: name, path: '', readonly: true, initial: { amount: r.amount, credit_amount: r.credit_amount, lines: await all('/business/payments/', { entry: r.id }) }, fields: [
    // 余额的三个来源都在这里：原金额减冲减、再减下面的流水合计。列表只留待结算。
    t('amount', '原金额'),
    // 冲减不产生收付流水，列表不再单列展示，只在确有冲减时在此说明余额的来源。
    ...(Number(r.credit_amount) ? [t('credit_amount', '冲减（取消费用或合同抵减，不产生流水）')] : []),
    { key: 'lines', label: '收付流水', type: 'rows', fields: [t('id', '流水ID'), t('date', '日期'), t('amount', '金额'), t('method', '方式'), t('account', '账户'), t('reference', '银行流水号'), t('reason', '说明'), t('reversal_of', '冲销原记录'), t('document', '凭证ID')] },
  ] }
  if (name === '调整到期日') return {
    title: name, subject: r.title, path: `/business/entries/${r.id}/adjust-due-date/`, submitLabel: '确认调整到期日',
    fields: [
      { key: 'current_due_date', label: '当前到期日', readonly: true, displayOnly: true },
      date('due_date', '新到期日'),
      { ...reason, label: '调整原因', hint: '写明合同约定与实际依据，如「合同约定发货后 30 天付款，实际 2026-11-11 发货」。' },
    ],
    initial: { current_due_date: r.due_date || '—', due_date: r.due_date || '' },
    prepare: data => ({ due_date: data.due_date, reason: data.reason, expected_due_date: r.due_date }),
    notice: { type: 'info', text: '只调整本应收节点的到期日，金额和已收流水不变；调整前后日期与原因写入操作审计。合同约定发货 / 验收后若干天付款时，按实际发生日调整。' },
  }
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  let prepare: Command['prepare']
  const routes: Record<string, string> = {
    登记收付款: 'pay',
    退款: 'refund',
    取消费用: 'cancel-expense',
    冲销付款: 'reverse',
  }
  if (routes[name]) path += routes[name] + '/'
  // 行按钮写的是「登记收款 / 登记付款」，对话框标题与提交按钮保持一致，并在顶部显示往来单位、项目、原金额与余额。
  const refund = name === '退款'
  const title = refund ? name : r.kind === 'receivable' ? '登记收款' : '登记付款'
  let notice: Command['notice']
  if (['登记收付款', '退款'].includes(name)) {
    const overdue = r.status === 'overdue'
    const balanceText = formatMoney(String(r.balance ?? '').replace(/^-/, ''))
    notice = { type: overdue ? 'warning' : 'info', text: [
      r.partner_name, r.project_name, r.amount != null ? `原金额 ${formatMoney(r.amount)}` : '',
      `${refund ? '待退款' : r.kind === 'receivable' ? '待收' : '待付'} ${balanceText}`,
      r.due_date ? `到期 ${r.due_date}${overdue ? '（已逾期）' : ''}` : '',
    ].filter(Boolean).join(' · ') }
    const docs = await all('/business/documents/', { project: r.project, category: 'receipt' })
    fields = [t('amount', '金额（元）'), date(), refund ? reason : optionalReason(undefined, `选填；不填按「${title}」记录`), { key: 'method', label: '结算方式', type: 'select', optional: true, options: [{ value: 'bank', label: '银行转账' }, { value: 'cash', label: '现金' }, { value: 'other', label: '其他' }] }, t('account', '账户标识', true), t('reference', '银行流水号', true), { key: 'document', label: '结算凭证', type: 'select', upload: { context: { project: r.project }, category: 'receipt' }, optional: true, options: docs.map(d => ({ value: d.id, label: d.original_name })) }]
    initial = { amount: String(r.balance).replace(/^-/, '') }
    const statements = await all('/business/reconciliations/', { entry: r.id, status: 'confirmed' })
    const eligible = statements.filter(s => s.valid && Number(s.remaining_amount) > 0 && (s.kind === 'refund') === (name === '退款'))
    if ((r.purchase || name === '退款') && !eligible.length) return {
      title, path, fields: [], subject: r.title,
      blocked: name === '退款' ? '尚无可用的已确认退款对账单。请先生成退款对账并确认，再登记退款。' : '尚无可用的已确认对账或预付款核准。已收货款先对账；未收货预付款按合同申请核准。',
      alternatives: [{ label: '生成对账单', open: () => entryReconciliationCommand(r) }, ...(r.purchase && name !== '退款' ? [{ label: '申请预付款核准', open: () => entryReconciliationCommand(r, true) }] : [])],
      links: [{ label: '查看已有对账与核准', path: `/projects/${r.project}?tab=finance&section=reconciliations` }],
    }
    fields.push({ key: 'reconciliation', label: '已确认对账 / 预付款核准', type: 'select', optional: !(r.purchase || name === '退款'), options: eligible.map(s => ({ value: s.id, label: `${s.code} · 可用 ${formatMoney(s.remaining_amount)} · 本次默认 ${formatMoney(cappedAmount(r.balance, s.remaining_amount))}` })), hint: r.purchase || name === '退款' ? '先从款项操作生成对账单，再到业务对账页确认。预付款由项目经理或管理员核准。' : '客户到账可直接登记，不强制先对账。' })
    if (eligible.length === 1) {
      initial.reconciliation = eligible[0]!.id
      initial.amount = cappedAmount(r.balance, eligible[0]!.remaining_amount)
      fields[0] = { ...fields[0]!, hint: `对账剩余额度 ${formatMoney(eligible[0]!.remaining_amount)} 元；本次最多 ${formatMoney(initial.amount)} 元，可按实际收付填写更小金额。` }
    } else if (eligible.length > 1) {
      initial.amount = ''
      fields[0] = { ...fields[0]!, optional: true, placeholder: '留空使用所选对账的本次默认金额', hint: `每张对账选项显示本次默认金额。留空时按所选对账默认值登记；手工填写时使用填写金额。${r.purchase || name === '退款' ? '' : `不选对账时默认 ${formatMoney(amount(cents(r.balance)))} 元。`}` }
      prepare = data => {
        if (data.amount != null && String(data.amount).trim() !== '') return data
        const selected = eligible.find(statement => String(statement.id) === String(data.reconciliation))
        if (!selected && (r.purchase || name === '退款' || data.reconciliation)) throw new Error('请选择有效的已确认对账单。')
        return { ...data, amount: selected ? cappedAmount(r.balance, selected.remaining_amount) : amount(cents(r.balance)) }
      }
    }
  }
  if (name === '冲销付款') fields = [date(), reason]
  if (refund) return { title, path, fields, initial, method, readonly, prepare, notice }
  if (name === '登记收付款') return { title, submitLabel: `${title}记录`, path, fields, initial, method, readonly, prepare, notice }
  return { title: name, path, fields, initial, method, readonly, prepare }
}
