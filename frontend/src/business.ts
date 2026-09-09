import * as projects from './modules/projects'
import * as bom from './modules/bom'
import * as purchases from './modules/purchases'
import * as inventory from './modules/inventory'
import * as finance from './modules/finance'
import * as masterdata from './modules/masterdata'
import * as settings from './modules/settings'
import * as documents from './modules/documents'
import { salesColumns, salesActions, salesCommand } from './modules/sales'
import { manager } from './session'
import type { Command, Row, Column } from './types'
export { endpoint, display, labels } from './modules/shared'
export { bomCommand } from './modules/bom'
export { shortageCommand } from './modules/purchases'
import { buyer, warehouse, finance as financeRole } from './modules/shared'
export const permission = { buyer, warehouse, finance: financeRole }
const modules = { projects, bom, purchases, inventory, finance, masterdata, settings, documents }
const owners: Record<string, keyof typeof modules> = {
  projects: 'projects',
  tasks: 'projects',
  deliveries: 'projects',
  time: 'projects',
  bom: 'bom',
  purchases: 'purchases',
  stocks: 'inventory',
  moves: 'inventory',
  entries: 'finance',
  payments: 'finance',
  items: 'masterdata',
  partners: 'masterdata',
  users: 'settings',
  company: 'settings',
  codes: 'settings',
  audit: 'settings',
  documents: 'documents',
}
function definition(resource: string) {
  const module = modules[owners[resource]]
  if (!module) throw new Error('未知资源：' + resource)
  return module
}
export const columns: Record<string, Column[]> = {
  sales: salesColumns,
  ...projects.columns,
  ...bom.columns,
  ...purchases.columns,
  ...inventory.columns,
  ...finance.columns,
  ...masterdata.columns,
  ...settings.columns,
  ...documents.columns,
}
export function createLabel(resource: string) {
  return resource === 'sales'
    ? manager()
      ? '新建销售'
      : ''
    : definition(resource).createLabel(resource)
}
export function createCommand(resource: string, projectId?: number): Promise<Command> {
  return resource === 'sales'
    ? salesCommand()
    : definition(resource).createCommand(resource, projectId)
}
export function actionNames(resource: string, row: Row) {
  return resource === 'sales' ? salesActions(row) : definition(resource).actionNames(resource, row)
}
export function actionCommand(resource: string, row: Row, name: string): Promise<Command> {
  return resource === 'sales'
    ? salesCommand(row, name)
    : definition(resource).actionCommand(resource, row, name)
}
