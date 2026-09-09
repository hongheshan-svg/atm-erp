import { all } from '../api'
import { options } from '../catalog'
import { can, manager } from '../session'
import { today } from '../forms'
import type { Command, Field, Row, Column } from '../types'
export const salesColumns: Column[] = [
  { key: 'code', label: '销售单号' },
  { key: 'name', label: '销售名称' },
  { key: 'customer_name', label: '客户' },
  { key: 'status', label: '状态' },
  { key: 'quote_amount', label: '报价金额' },
  { key: 'contract_amount', label: '合同金额' },
  { key: 'project_code', label: '执行项目' },
]
export function salesActions(row: Row): string[] {
  if (!can(['admin', 'manager', 'finance'])) return []
  if (!manager() || !['draft', 'quoted'].includes(row.status)) return ['查看明细']
  return row.status === 'quoted' ? ['查看明细', '编辑销售', '报价', '签约', '取消销售'] : ['查看明细', '编辑销售', '报价', '取消销售']
}
const reason: Field = { key: 'reason', label: '原因 / 说明' }
export async function salesCommand(row?: Row, action?: string): Promise<Command> {
  const path = '/business/sales/'
  if (row && action === '查看明细') return {
    title: '销售明细', path: `${path}${row.id}/`, readonly: true, initial: row,
    fields: [
      { key: 'code', label: '销售单号' }, { key: 'name', label: '销售名称' },
      { key: 'customer_name', label: '客户' }, { key: 'manager_name', label: '负责人' },
      { key: 'requirements', label: '需求说明', type: 'textarea', optional: true },
      { key: 'due_date', label: '计划交期', optional: true },
      { key: 'equipment_quantity', label: '设备数量' }, { key: 'warranty_months', label: '质保月数' },
      { key: 'quote_amount', label: '报价金额（元）' }, { key: 'contract_amount', label: '合同金额（元）' },
      { key: 'contract_date', label: '签约日期', optional: true }, { key: 'project_code', label: '执行项目', optional: true },
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
        { key: 'manager', label: '负责人', type: 'select', options: options(users) },
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
      ...(!row.project
        ? [
            {
              key: 'manager',
              label: '项目负责人',
              type: 'select' as const,
              options: options(users),
              initial: row.manager,
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
    initial: { milestones: [{ title: '合同款', amount: row.quote_amount, due_date: today() }] },
  }
}
