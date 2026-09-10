import { all, read, download } from '../api'
import { options } from '../catalog'
import { can, manager, user, salesOnly, hasRoles } from '../session'
import { today } from '../forms'
import type { Command, Field, Row, Column } from '../types'
import { display } from './shared'
export const salesColumns: Column[] = [
  { key: 'code', label: '销售单号' },
  { key: 'contract_number', label: '合同编号' },
  { key: 'name', label: '销售名称' },
  { key: 'customer_name', label: '客户' },
  { key: 'status', label: '状态' },
  { key: 'quote_amount', label: '报价金额' },
  { key: 'contract_amount', label: '合同金额' },
  { key: 'project_code', label: '执行项目' },
]
export function salesActions(row: Row): string[] {
  const actions = salesBusinessActions(row)
  return actions.length ? [...actions, '附件'] : actions
}
function salesBusinessActions(row: Row): string[] {
  if (salesOnly() && row.manager === user.value?.id) return row.status === 'signed' ? ['查看明细', '交付与回款'] : ['draft', 'quoted'].includes(row.status) ? ['查看明细', '编辑销售', '报价', ...(row.status === 'quoted' ? ['签约'] : []), '取消销售'] : ['查看明细']
  if (!can(['admin', 'manager', 'finance'])) return []
  if (row.status === 'signed') return ['查看明细', '补充协议记录', ...(manager() ? ['签订补充协议'] : [])]
  if (!manager() || !['draft', 'quoted'].includes(row.status)) return ['查看明细']
  return row.status === 'quoted' ? ['查看明细', '编辑销售', '报价', '签约', '取消销售'] : ['查看明细', '编辑销售', '报价', '取消销售']
}
const reason: Field = { key: 'reason', label: '原因 / 说明' }
export async function salesCommand(row?: Row, action?: string): Promise<Command> {
  const path = '/business/sales/'
  if (row && action === '交付与回款') {
    const data = await read(`${path}${row.id}/progress/`)
    return { title: '交付与回款', path: '', readonly: true, initial: { ...data, project_status: display(data.project_status) }, fields: [
      { key: 'project_status', label: '项目状态' },
      { key: 'deliveries', label: '交付批次', type: 'rows', fields: [{ key: 'code', label: '批次' }, { key: 'quantity', label: '数量' }, { key: 'shipped_date', label: '发货日期' }, { key: 'accepted_date', label: '验收日期' }] },
      { key: 'receivables', label: '应收与回款', type: 'rows', fields: [{ key: 'title', label: '款项' }, { key: 'balance', label: '待收 / 待退' }, { key: 'paid', label: '净回款' }, { key: 'amount', label: '原应收' }, { key: 'credit_amount', label: '已抵减' }, { key: 'due_date', label: '到期日' }] },
    ], notice: { type: 'info', text: '复用交付和财务记录；负余额表示待退款。销售经理只读，收款登记与纠错由财务处理。' } }
  }
  if (row && action === '补充协议记录') {
    const records = await read(`${path}${row.id}/amendments/`)
    const describe = (values: Row) => Object.entries(values).map(([key, value]) => `${({ amount: '合同金额', equipment_quantity: '设备数量', warranty_months: '质保月数' } as Record<string, string>)[key] || key}：${value}`).join('；')
    return { title: action, path: '', readonly: true, initial: { lines: records.map((r: Row) => ({ ...r, before_text: describe(r.before), after_text: describe(r.after) })) }, fields: [{ key: 'lines', label: '补充协议', type: 'rows', fields: [{ key: 'date', label: '日期' }, { key: 'reason', label: '原因' }, { key: 'before_text', label: '变更前' }, { key: 'after_text', label: '变更后' }, { key: 'document__original_name', label: '合同附件' }] }], actions: records.map((r: Row) => ({ label: `下载 ${r.document__original_name}`, run: async () => { const doc = await read(`/business/documents/${r.document}/`); await download(doc.download_url, doc.original_name) } })) }
  }
  if (row && action === '签订补充协议') {
    const [detail, docs, entries] = await Promise.all([read(`${path}${row.id}/`), all('/business/documents/', { project: row.project, category: 'contract' }), all('/business/entries/', { project: row.project, kind: 'receivable' })])
    return { title: action, path: `${path}${row.id}/amend/`, fields: [
      { key: 'amount', label: '变更后合同总额（元）' }, { key: 'equipment_quantity', label: '变更后设备数量' }, { key: 'warranty_months', label: '后续批次质保月数' }, { key: 'date', label: '协议日期', type: 'date' }, reason,
      { key: 'document', label: '补充协议附件（先在销售或项目附件上传）', type: 'select', options: docs.filter(d => !d.purchase).map(d => ({ value: d.id, label: d.original_name })) },
      { key: 'milestones', label: '增额收款节点（仅增加金额时填写）', type: 'rows', optional: true, fields: [{ key: 'title', label: '款项名称' }, { key: 'amount', label: '增加金额' }, { key: 'due_date', label: '期限', type: 'date' }] },
      { key: 'credits', label: '原合同款抵减（仅减少金额时填写）', type: 'rows', optional: true, fields: [{ key: 'entry', label: '原合同款', type: 'select', options: entries.filter(e => !e.task && !e.cancelled).map(e => ({ value: e.id, label: `${e.title} · 原金额 ${e.amount} · 已抵减 ${e.credit_amount}` })) }, { key: 'amount', label: '抵减金额' }] },
    ], initial: { amount: detail.contract_amount, equipment_quantity: detail.equipment_quantity, warranty_months: detail.warranty_months, date: today(), milestones: [], credits: [] }, prepare: data => ({ ...data, expected_updated_at: detail.updated_at }), notice: { type: 'info', text: '原合同与协议记录保留。增额节点合计或减额抵减合计必须等于差额；已收款抵减后形成待退款。已交付批次质保不变，已发货不能修改设备总数。' } }
  }
  if (row && action === '查看明细') return {
    title: '销售明细', path: `${path}${row.id}/`, readonly: true, initial: row,
    fields: [
      { key: 'code', label: '销售单号' }, { key: 'name', label: '销售名称' },
      { key: 'customer_name', label: '客户' }, { key: 'manager_name', label: '负责人' },
      { key: 'requirements', label: '需求说明', type: 'textarea', optional: true },
      { key: 'due_date', label: '计划交期', optional: true },
      { key: 'equipment_quantity', label: '设备数量' }, { key: 'warranty_months', label: '质保月数' },
      { key: 'quote_amount', label: '报价金额（元）' }, { key: 'contract_amount', label: '合同金额（元）' },
      { key: 'original_contract_amount', label: '原签约金额（元）', optional: true },
      { key: 'contract_date', label: '签约日期', optional: true }, { key: 'project_code', label: '执行项目', optional: true },
      { key: 'contract_number', label: '合同编号', optional: true },
    ],
  }
  if (!row || action === '编辑销售') {
    const [partners, users] = await Promise.all([
      all('/business/partners/', { is_active: true }),
      all('/auth/directory/'),
    ])
    return {
      title: row ? '编辑销售' : '新建销售',
      path: row ? `${path}${row.id}/edit/` : path,
      initial: row,
      prepare: row ? data => ({ ...data, expected_updated_at: row.updated_at }) : undefined,
      fields: [
        { key: 'name', label: '销售名称' },
        {
          key: 'customer',
          label: '客户',
          type: 'select',
          options: options(partners.filter((p) => p.kind !== 'supplier')),
        },
        { key: 'manager', label: '负责人', type: 'select', initial: user.value?.id, options: options(users.filter(u => salesOnly() ? u.id === user.value?.id : hasRoles(u, ['admin', 'manager', 'sales_manager']))) },
        { key: 'requirements', label: '需求说明', type: 'textarea', optional: true },
        { key: 'due_date', label: '计划交期', type: 'date', optional: true },
        { key: 'equipment_quantity', label: '设备数量', initial: 1 },
        { key: 'warranty_months', label: '质保月数', initial: 12 },
        ...(row ? [{ ...reason, hint: '保存修改后需重新报价，旧报价保留在操作审计中。' }] : []),
      ],
    }
  }
  if (action === '报价')
    return {
      title: action,
      path: `${path}${row.id}/quote/`,
      fields: [{ key: 'amount', label: '报价金额（元）' }, reason],
      initial: { amount: row.quote_amount },
    }
  if (action === '取消销售')
    return { title: action, path: `${path}${row.id}/cancel/`, fields: [reason] }
  if (action !== '签约') throw new Error('不支持的销售操作。')
  const users = row.project ? [] : await all('/auth/directory/')
  return {
    title: '签约',
    path: `${path}${row.id}/sign/`,
    fields: [
      { key: 'date', label: '日期', type: 'date', initial: today() },
      { key: 'contract_number', label: '合同编号（按签署合同填写）', optional: true },
      ...(!row.project
        ? [
            {
              key: 'manager',
              label: '项目负责人',
              type: 'select' as const,
              options: options(users.filter(u => hasRoles(u, ['admin', 'manager']))),
              initial: salesOnly() ? undefined : row.manager,
            },
            {
              key: 'members',
              label: '项目成员',
              type: 'multi' as const,
              options: options(users),
              optional: true,
            },
          ]
        : []),
      {
        key: 'milestones',
        label: '收款节点',
        type: 'rows',
        fields: [
          { key: 'title', label: '节点名称' },
          { key: 'amount', label: '金额（元）' },
          { key: 'due_date', label: '期限', type: 'date' },
        ],
      },
    ],
    initial: { milestones: [{ title: '合同款', amount: row.quote_amount, due_date: '' }] },
    notice: { type: 'info', text: '按签署合同拆分预付款、发货款、验收款及质保尾款，节点合计须等于报价金额；填写合同约定的收款日期，签约后自动建立执行项目。' },
  }
}
