import { options } from '../catalog'
import { can } from '../session'
import { today } from '../forms'
import type { Catalog } from '../catalog'
import type { Field } from '../types'
import type { Column } from '../types'
import type { Option } from '../types'
import type { Row } from '../types'
export const ledgerStatus = (row: Row) => row.reversal_of ? '冲销记录' : row.reversed_by ? '已冲销' : '有效'
export const t = (key: string, label: string, optional = false): Field => ({ key, label, optional })
export const date = (key = 'date', label = '日期', optional = false): Field => ({
  key,
  label,
  type: 'date',
  initial: ['date', 'received_date'].includes(key) ? today() : '',
  optional,
})
export const select = (key: string, label: string, opts: Option[], optional = false): Field => ({
  key,
  label,
  type: 'select',
  options: opts,
  optional,
})
export const choices = (values: Record<string, string>): Option[] =>
  Object.entries(values).map(([value, label]) => ({ value, label }))
export const rows = (key: string, label: string, fields: Field[]): Field => ({
  key,
  label,
  type: 'rows',
  fields,
})
export const reason = t('reason', '原因 / 说明')
export const qty = t('quantity', '数量')
export const price = t('unit_price', '含税单价（元）')
export const buyer = () => can(['admin', 'manager', 'purchaser'])
export const warehouse = () => can(['admin', 'warehouse'])
export const finance = () => can(['admin', 'finance'])
export const C = (key: string, label: string): Column => ({ key, label })
export const project = (c: Catalog): Field =>
  select(
    'project',
    '项目',
    options(
      c.projects.filter((p) => !['draft', 'quoted', 'closed', 'cancelled'].includes(p.status)),
    ),
  )
export const person = (c: Catalog, key = 'assignee', label = '执行人') =>
  select(key, label, options(c.users))
export const item = (c: Catalog) => select('item', '物料', options(c.items))

export function endpoint(resource: string) {
  return `${['users'].includes(resource) ? '/auth/' : ['company', 'codes', 'audit'].includes(resource) ? '/core/' : '/business/'}${resource}/`
}
export const labels: Record<string, string> = {
  bank: '银行转账', cash: '现金',
  signed: '已签约',
  draft: '草稿',
  quoted: '已报价',
  active: '执行中',
  delivering: '交付中',
  warranty: '已验收',
  closed: '已结项',
  cancelled: '已取消',
  submitted: '待批准',
  approved: '待收货',
  partial: '部分收货',
  received: '已收货',
  open: '待完成',
  done: '已完成',
  design: '设计',
  assembly: '装配',
  test: '调试',
  install: '安装',
  acceptance: '验收',
  service: '售后',
  opening: '期初',
  receipt: '采购收货',
  issue: '项目领料',
  return: '项目退料',
  purchase_return: '采购退货',
  count: '盘点',
  receivable: '应收',
  payable: '应付',
  expense: '费用',
  customer: '客户',
  supplier: '供应商',
  both: '客户及供应商',
  admin: '管理员',
  manager: '项目经理',
  sales_manager: '销售经理',
  purchaser: '采购员',
  warehouse: '仓管',
  finance: '财务',
  reconciliation: '对账单',
  member: '成员',
  drawing: '图纸',
  contract: '合同',
  delivery: '交付',
  other: '其他',
}
export function display(value: any) {
  if (value == null || value === '') return '—'
  if (typeof value === 'boolean') return value ? '启用' : '停用'
  if (typeof value === 'object') return JSON.stringify(value)
  return labels[String(value)] || String(value)
}
