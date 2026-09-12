import { afterEach, describe, expect, it } from 'vitest'
import { bomEditor, canImportResource, materialEditor, money, partnerEditor, productionProject, purchaseApprover, purchasing, reports, roleLabels, taskManager, timeAmender, user } from './session'
import { navigation } from './navigation'
import { actionNames, createLabel } from './business'
import { userFields } from './modules/settings'
import { resourceFilters } from './resource-ui'

afterEach(() => { user.value = null })

describe('固定岗位与权限并集', () => {
  const oldNavigation: Record<string, string[]> = {
    admin: ['workbench', 'reports', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'],
    manager: ['workbench', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'],
    sales_manager: ['workbench', 'sales', 'masterdata', 'settings'],
    purchaser: ['workbench', 'projects', 'bom', 'purchases', 'inventory', 'masterdata', 'settings'],
    warehouse: ['workbench', 'projects', 'bom', 'purchases', 'inventory', 'masterdata', 'settings'],
    finance: ['workbench', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'],
    member: ['workbench', 'projects', 'bom', 'masterdata', 'settings'],
  }
  for (const [role, pages] of Object.entries(oldNavigation)) it(`原岗位 ${role} 菜单保持不变`, () => {
    user.value = { roles: [role] }
    expect(navigation().map(page => page.key)).toEqual(pages)
  })

  it('用户创建、筛选与标签共用十一个固定岗位', () => {
    expect(roleLabels).toMatchObject({ purchase_manager: '采购经理', mechanical_engineer: '机械工程师', electrical_engineer: '电气工程师', production_manager: '生产经理', member: '普通成员' })
    expect(Object.keys(roleLabels)).toHaveLength(11)
    expect(userFields.find(field => field.key === 'roles')?.options).toEqual(Object.entries(roleLabels).map(([value, label]) => ({ value, label })))
    expect(resourceFilters.users?.options).toEqual(roleLabels)
  })

  it('采购经理全局采购审批依服务端行权限，不取得其他经营管理权限', () => {
    user.value = { id: 4, roles: ['purchase_manager'], management_reports: true }
    expect(navigation().map(page => page.key)).toEqual(oldNavigation.purchaser)
    expect(purchasing()).toBe(true)
    expect(materialEditor()).toBe(true)
    expect(partnerEditor()).toBe(true)
    expect(money()).toBe(false)
    expect(reports()).toBe(false)
    expect(createLabel('projects')).toBe('')
    expect(createLabel('sales')).toBe('')
    expect(createLabel('tasks')).toBe('')
    expect(actionNames('projects', { status: 'active', can_manage: false })).toEqual([])
    expect(purchaseApprover({ can_manage: false, can_approve: true })).toBe(true)
    expect(purchaseApprover({ can_manage: true, can_approve: false })).toBe(false)
    expect(purchaseApprover({})).toBe(false)
    expect(actionNames('purchases', { status: 'submitted', can_manage: false, can_approve: true })).toEqual(expect.arrayContaining(['批准采购', '退回修改']))
    expect(actionNames('reconciliations', { status: 'draft', valid: true, kind: 'prepayment' })).not.toContain('确认对账')
    expect(bomEditor({ can_edit_bom: true })).toBe(false)
  })

  for (const role of ['mechanical_engineer', 'electrical_engineer']) it(`${role} 仅参与项目技术操作与本人任务`, () => {
    user.value = { id: 5, roles: [role] }
    expect(navigation().map(page => page.key)).toEqual(oldNavigation.member)
    expect(createLabel('items')).toBe('新增物料')
    expect(createLabel('partners')).toBe('')
    expect(createLabel('tasks')).toBe('')
    expect(createLabel('purchases')).toBe('')
    expect(createLabel('projects')).toBe('')
    expect(actionNames('items', {})).toEqual(['编辑'])
    expect(actionNames('partners', { kind: 'supplier' })).toEqual([])
    expect(actionNames('tasks', { status: 'open', kind: 'design', assignee: 5 })).toEqual(['登记工时', '完成任务'])
    expect(actionNames('tasks', { status: 'open', kind: 'design', assignee: 9 })).toEqual([])
    expect(actionNames('projects', { status: 'active', can_manage: false })).toEqual([])
    expect(actionNames('bom', { can_edit_bom: true })).toEqual(['移除'])
    expect(actionNames('bom', { can_edit_bom: false })).toEqual([])
    expect(actionNames('bom', {})).toEqual([])
    expect(canImportResource('items')).toBe(true)
    expect(canImportResource('time')).toBe(true)
    for (const resource of ['partners', 'purchases', 'tasks', 'projects', 'entries', 'moves']) expect(canImportResource(resource)).toBe(false)
  })

  it('工程师兼任采购仅扩展采购业务，BOM写入仍取当前项目授权', () => {
    user.value = { id: 5, roles: ['mechanical_engineer', 'purchaser'] }
    expect(navigation().map(page => page.key)).toEqual(oldNavigation.purchaser)
    expect(canImportResource('purchases')).toBe(true)
    expect(canImportResource('partners')).toBe(true)
    expect(bomEditor({ can_edit_bom: false })).toBe(false)
    expect(bomEditor({ can_edit_bom: true })).toBe(true)
    expect(purchaseApprover({ can_approve: true })).toBe(false)
    expect(money()).toBe(false)
  })

  it('生产经理仅管理参与项目生产任务，兼采购不扩展生产写入范围', () => {
    user.value = { id: 8, roles: ['production_manager'], management_reports: true }
    expect(navigation().map(page => page.key)).toEqual(oldNavigation.member)
    expect(createLabel('tasks')).toBe('新建任务')
    for (const resource of ['projects', 'purchases', 'sales', 'items', 'partners']) expect(createLabel(resource)).toBe('')
    expect(bomEditor({ can_edit_bom: true })).toBe(false)
    expect(money()).toBe(false)
    expect(reports()).toBe(false)
    expect(canImportResource('time')).toBe(true)
    expect(productionProject({ can_manage_production: true })).toBe(true)
    expect(productionProject({})).toBe(false)
    expect(taskManager({ kind: 'assembly', can_manage: true })).toBe(true)
    expect(taskManager({ kind: 'design', can_manage: true })).toBe(false)
    expect(timeAmender({ user: 9, can_amend: true })).toBe(true)
    expect(timeAmender({ user: 9, can_amend: false })).toBe(false)
    user.value = { id: 8, roles: ['production_manager', 'purchaser'] }
    expect(navigation().map(page => page.key)).toEqual(oldNavigation.purchaser)
    expect(productionProject({ can_manage_production: false })).toBe(false)
    expect(taskManager({ kind: 'assembly', can_manage: false })).toBe(false)
    expect(taskManager({ kind: 'assembly' })).toBe(false)
    expect(timeAmender({ user: 9 })).toBe(false)
  })
})
