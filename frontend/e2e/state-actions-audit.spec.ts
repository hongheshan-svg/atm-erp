import type { Browser, BrowserContext, TestInfo } from '@playwright/test'
import { test, expect, login, observePage, expectHttpError, type Page, type Locator } from './fixtures'

// The period-lock case changes an installation-wide setting. Run this file with
// the configured single worker, without another E2E process sharing the database.
test.describe.configure({ mode: 'serial' })
const password = 'State-actions-audit-2026-only'
const contexts: BrowserContext[] = []
const errors: string[] = []
type Account = { id: number; username: string; display_name: string }
const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, text: string) => page.locator('.el-table__body tr:visible').filter({ hasText: text })
const day = (offset = 0) => {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

async function api(page: Page, path: string, data?: Record<string, unknown>, status = 200) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() }
  const response = data === undefined
    ? await page.request.get(`/api/${path}`, { headers })
    : await page.request.post(`/api/${path}`, { headers, data })
  expect(response.status(), await response.text()).toBe(status)
  return response.json()
}

async function account(page: Page, role: string, suffix: string): Promise<Account> {
  return api(page, 'auth/users/', {
    username: `state_${role}_${suffix}`, display_name: `状态验收${role}${suffix}`,
    roles: [role], password, hourly_cost: '20.00',
  }, 201)
}

async function session(browser: Browser, info: TestInfo, person: Account) {
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL, viewport: info.project.use.viewport,
    isMobile: info.project.use.isMobile, hasTouch: info.project.use.hasTouch,
  })
  contexts.push(context)
  const page = await context.newPage()
  observePage(page, errors)
  await login(page, person.username, password)
  return page
}

async function project(page: Page, suffix: string, manager: number, members: number[] = []) {
  const customer = await api(page, 'business/partners/', { name: `状态客户${suffix}`, kind: 'customer' }, 201)
  return api(page, 'business/projects/', {
    name: `状态动作验收${suffix}`, customer: customer.id, manager, members,
  }, 201)
}

async function action(page: Page, target: Locator, name: string) {
  await target.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(page)).toBeVisible()
}

async function submit(page: Page, path: string, status = 200) {
  if (status >= 400) expectHttpError(page, `/api/${path}`, status)
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === `/api/${path}` && response.request().method() === 'POST')
  await dialog(page).getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(status)
  if (status < 300) await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  else await expect(dialog(page).getByRole('alert')).toBeVisible()
}

async function reason(page: Page, text: string) {
  await dialog(page).getByLabel('原因 / 说明', { exact: true }).fill(text)
}

test.beforeEach(async ({ page }) => {
  errors.length = 0
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
})

test.afterEach(async () => {
  for (const context of contexts.splice(0)) await context.close()
  expect(errors, '额外角色浏览器不应出现异常或未预期的警告').toEqual([])
})

test('仓管盘点拒绝过期快照，刷新后实盘并保留数量与成本流水', async ({ page, browser }, info) => {
  const suffix = String(Date.now())
  const person = await account(page, 'warehouse', suffix)
  const itemName = `盘点伺服电机${suffix}`
  const item = await api(page, 'business/items/', { code: `COUNT-${suffix}`, name: itemName }, 201)
  await api(page, 'business/stocks/opening/', { item: item.id, quantity: '5', unit_cost: '20', reason: '盘点验收期初' })
  const stock = (await api(page, `business/stocks/?item=${item.id}`)).results[0]
  const warehouse = await session(browser, info, person)
  await warehouse.goto('/erp/inventory?section=stocks')
  await action(warehouse, row(warehouse, itemName), '盘点')
  await dialog(warehouse).getByLabel('实盘数量', { exact: true }).fill('4')
  await reason(warehouse, '旧快照不应覆盖另一人盘点')
  await api(page, `business/stocks/${stock.id}/count/`, {
    quantity: '6', expected_quantity: stock.quantity, expected_updated_at: stock.updated_at, reason: '另一人先完成盘点',
  })
  await submit(warehouse, `business/stocks/${stock.id}/count/`, 409)
  await expect(dialog(warehouse).getByRole('alert')).toContainText('盘点期间库存发生变化')
  expect(await api(page, `business/stocks/${stock.id}/`)).toMatchObject({ quantity: '6.000', value: '120.00' })
  expect((await api(page, `business/moves/?stock=${stock.id}&kind=count`)).count).toBe(1)
  await dialog(warehouse).getByRole('button', { name: '取消', exact: true }).click()
  await warehouse.reload()
  await action(warehouse, row(warehouse, itemName), '盘点')
  await expect(dialog(warehouse).getByLabel('实盘数量', { exact: true })).toHaveValue('6.000')
  await dialog(warehouse).getByLabel('实盘数量', { exact: true }).fill('4')
  await reason(warehouse, '重新核对实盘四件')
  await submit(warehouse, `business/stocks/${stock.id}/count/`)
  await expect(row(warehouse, itemName)).toContainText('4.000')
  expect(await api(page, `business/stocks/${stock.id}/`)).toMatchObject({ quantity: '4.000', value: '80.00' })
  const moves = await api(page, `business/moves/?stock=${stock.id}&kind=count`)
  expect(moves.count).toBe(2)
  expect(moves.results).toEqual(expect.arrayContaining([
    expect.objectContaining({ quantity: '1.000', value: '20.00', reason: '另一人先完成盘点' }),
    expect.objectContaining({ quantity: '-2.000', value: '-40.00', created_by: person.id }),
  ]))
  expect(await api(warehouse, `business/stocks/${stock.id}/`)).not.toHaveProperty('value')
  await warehouse.screenshot({ path: info.outputPath('stock-count.png'), animations: 'disabled' })
})

test('仓管采购退货同步库存与应付抵减，超退失败不留重复流水', async ({ page, browser }, info) => {
  const suffix = String(Date.now())
  const person = await account(page, 'warehouse', suffix)
  const admin = await api(page, 'auth/me/')
  const current = await project(page, suffix, admin.id)
  const itemName = `退货气缸${suffix}`
  const item = await api(page, 'business/items/', { code: `RETURN-${suffix}`, name: itemName }, 201)
  const supplier = await api(page, 'business/partners/', { name: `退货供应商${suffix}`, kind: 'supplier' }, 201)
  const purchase = await api(page, 'business/purchases/', {
    project: current.id, supplier: supplier.id, due_date: day(),
    lines: [{ item: item.id, quantity: '3', unit_price: '100' }],
  }, 201)
  await api(page, `business/purchases/${purchase.id}/submit/`, {})
  await api(page, `business/purchases/${purchase.id}/approve/`, { reason: '隔离验收管理员复核自建采购' })
  const order = await api(page, `business/purchases/${purchase.id}/`)
  await api(page, `business/purchases/${purchase.id}/receive/`, {
    received_date: day(), reason: '三件合格入库', lines: [{ line: order.lines[0].id, quantity: '3' }],
  })
  const receipt = (await api(page, `business/moves/?project=${current.id}&kind=receipt`)).results[0]
  const warehouse = await session(browser, info, person)
  await warehouse.goto('/erp/inventory?section=moves')
  await action(warehouse, row(warehouse, itemName).filter({ hasText: '采购收货' }), '采购退货')
  await dialog(warehouse).getByLabel('数量', { exact: true }).fill('1')
  await reason(warehouse, '尺寸不符供应商确认退一件')
  await submit(warehouse, `business/moves/${receipt.id}/return-purchase/`)
  await expect(row(warehouse, itemName).filter({ hasText: '采购退货' })).toContainText('-1.000')
  expect(await api(page, `business/stocks/${receipt.stock}/`)).toMatchObject({ quantity: '2.000', value: '200.00' })
  const entry = (await api(page, `business/entries/?project=${current.id}&kind=payable`)).results[0]
  expect(entry).toMatchObject({ amount: '300.00', credit_amount: '100.00', balance: '200.00' })
  expect((await api(page, `business/purchases/${purchase.id}/`)).lines[0].returned_quantity).toBe('1.000')
  const returned = await api(page, `business/moves/?project=${current.id}&kind=purchase_return`)
  expect(returned.count).toBe(1)
  expect(returned.results[0]).toMatchObject({ source: receipt.id, quantity: '-1.000', value: '-100.00', supplier_credit: '100.00', created_by: person.id })
  await action(warehouse, row(warehouse, itemName).filter({ hasText: '采购收货' }), '采购退货')
  await dialog(warehouse).getByLabel('数量', { exact: true }).fill('3')
  await reason(warehouse, '超退必须失败')
  await submit(warehouse, `business/moves/${receipt.id}/return-purchase/`, 409)
  await expect(dialog(warehouse).getByRole('alert')).toContainText('采购退货数量超过原收货可退余量')
  expect((await api(page, `business/moves/?project=${current.id}&kind=purchase_return`)).count).toBe(1)
  expect(await api(page, `business/stocks/${receipt.stock}/`)).toMatchObject({ quantity: '2.000', value: '200.00' })
  expect(await api(page, `business/entries/${entry.id}/`)).toMatchObject({ credit_amount: '100.00', balance: '200.00' })
  await warehouse.screenshot({ path: info.outputPath('purchase-return-rejected.png'), animations: 'disabled' })
  await dialog(warehouse).getByRole('button', { name: '取消', exact: true }).click()
  await warehouse.goto(`/erp/projects/${current.id}?tab=purchases`)
  await action(warehouse, row(warehouse, order.code), '登记采购质保')
  await dialog(warehouse).getByLabel('原收货批次', { exact: true }).selectOption(String(receipt.id))
  await dialog(warehouse).getByLabel('数量', { exact: true }).fill('1')
  await dialog(warehouse).getByLabel('故障描述', { exact: true }).fill('气缸密封失效，与供应商核对退货责任')
  await submit(warehouse, `business/purchases/${purchase.id}/warranty/`)
  const warranty = (await api(page, `business/purchases/${purchase.id}/warranty/`)).cases[0]
  expect(warranty).toMatchObject({ status: '待响应', quantity: '1.000', receipt: receipt.id, within_warranty: true })
  for (const [status, label, response] of [
    ['repairing', '维修中', '供应商已接收故障反馈，正在检查密封组件'],
    ['closed', '已关闭', '双方确认原批次退货退款完成，关闭质保事项'],
  ]) {
    await action(warehouse, row(warehouse, order.code), '处理采购质保')
    await dialog(warehouse).getByLabel('质保事项', { exact: true }).selectOption(String(warranty.id))
    await dialog(warehouse).getByLabel('处理结果', { exact: true }).selectOption(status!)
    await dialog(warehouse).getByLabel('供应商响应、责任与处理说明', { exact: true }).fill(response!)
    if (status === 'closed') {
      await dialog(warehouse).getByLabel('原批次退货流水', { exact: true }).selectOption(String(returned.results[0].id))
    }
    await submit(warehouse, `business/purchases/${purchase.id}/warranty/`)
    expect((await api(page, `business/purchases/${purchase.id}/warranty/`)).cases[0]).toMatchObject({ status: label, response })
  }
  const closed = (await api(page, `business/purchases/${purchase.id}/warranty/`)).cases[0]
  expect(closed.returned).toBe(returned.results[0].id)
  expect(closed.history).toHaveLength(3)
  await action(warehouse, row(warehouse, order.code), '质保记录')
  const warrantyRow = dialog(warehouse).locator('.el-table__body tr').filter({ hasText: '气缸密封失效' })
  await expect(warrantyRow).toContainText('已关闭')
  await expect(warrantyRow).toContainText('双方确认原批次退货退款完成，关闭质保事项')
  // Warranty handling must reference the existing return, without moving stock or crediting twice.
  expect((await api(page, `business/moves/?project=${current.id}&kind=purchase_return`)).count).toBe(1)
  expect(await api(page, `business/stocks/${receipt.stock}/`)).toMatchObject({ quantity: '2.000', value: '200.00' })
  expect(await api(page, `business/entries/${entry.id}/`)).toMatchObject({ credit_amount: '100.00', balance: '200.00' })
  await warehouse.screenshot({ path: info.outputPath('purchase-warranty-closed.png'), animations: 'disabled' })
})

test('项目经理重新分配、取消和重开任务，执行人权限与完成状态同步', async ({ page, browser }, info) => {
  const suffix = String(Date.now())
  const owner = await account(page, 'manager', suffix)
  const first = await account(page, 'member', `${suffix}a`)
  const second = await account(page, 'member', `${suffix}b`)
  const current = await project(page, suffix, owner.id, [first.id, second.id])
  const title = `设计状态验收${suffix}`
  const task = await api(page, 'business/tasks/', { project: current.id, kind: 'design', title, assignee: first.id }, 201)
  const manager = await session(browser, info, owner)
  const member = await session(browser, info, second)
  await manager.goto(`/erp/projects/${current.id}?tab=tasks&section=tasks`)
  await action(manager, row(manager, title), '重新分配')
  await dialog(manager).getByLabel('执行人', { exact: true }).selectOption(String(second.id))
  await reason(manager, '设计工作交接给另一成员')
  await submit(manager, `business/tasks/${task.id}/assign/`)
  expect(await api(page, `business/tasks/${task.id}/`)).toMatchObject({ status: 'open', assignee: second.id })
  await expect(row(manager, title)).toContainText(second.display_name)
  await action(manager, row(manager, title), '取消任务')
  await reason(manager, '范围确认暂时取消')
  await submit(manager, `business/tasks/${task.id}/cancel/`)
  await expect(row(manager, title)).toContainText('已取消')
  expect(await api(page, `business/tasks/${task.id}/`)).toMatchObject({ status: 'cancelled', assignee: second.id })
  await api(member, `business/tasks/${task.id}/time/`, { date: day(), hours: '1', reason: '已取消任务不可写工时' }, 409)
  expect((await api(page, `business/time/?task=${task.id}`)).count).toBe(0)
  await member.goto(`/erp/projects/${current.id}?tab=tasks&section=tasks`)
  await expect(row(member, title).getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  await action(manager, row(manager, title), '重开任务')
  await reason(manager, '恢复原设计范围')
  await submit(manager, `business/tasks/${task.id}/reopen/`)
  expect(await api(page, `business/tasks/${task.id}/`)).toMatchObject({ status: 'open', assignee: second.id, completed_at: null })
  await member.reload()
  await action(member, row(member, title), '完成任务')
  await reason(member, '新执行人完成设计确认')
  await submit(member, `business/tasks/${task.id}/complete/`)
  const done = await api(page, `business/tasks/${task.id}/`)
  expect(done.status).toBe('done')
  expect(done.completed_at).toBeTruthy()
  await manager.reload()
  await action(manager, row(manager, title), '重开任务')
  await reason(manager, '追加设计复核')
  await submit(manager, `business/tasks/${task.id}/reopen/`)
  expect(await api(page, `business/tasks/${task.id}/`)).toMatchObject({ status: 'open', assignee: second.id, completed_at: null })
  await expect(row(manager, title)).toContainText('待完成')
  await manager.screenshot({ path: info.outputPath('task-reopened.png'), animations: 'disabled' })
})

test('管理员页面锁账阻止成员跨期工时，重开后补录并保留审计', async ({ page, browser }, info) => {
  const suffix = String(Date.now())
  const person = await account(page, 'member', suffix)
  const admin = await api(page, 'auth/me/')
  const current = await project(page, suffix, admin.id, [person.id])
  const title = `跨期设计工时${suffix}`
  const task = await api(page, 'business/tasks/', { project: current.id, kind: 'design', title, assignee: person.id }, 201)
  const company = (await api(page, 'core/company/')).results[0]
  const member = await session(browser, info, person)
  const cutoff = day(-1)
  try {
    await page.goto('/erp/settings?section=company')
    await action(page, row(page, company.name), '锁账与重开')
    await dialog(page).getByLabel('锁账截止日期', { exact: true }).fill(cutoff)
    await dialog(page).getByLabel('锁账或重开原因', { exact: true }).fill(`锁账验收${suffix}`)
    await submit(page, `core/company/${company.id}/period-lock/`)
    expect((await api(page, 'core/company/')).results[0]).toMatchObject({ locked_through: cutoff, period_revision: company.period_revision + 1 })
    await member.goto(`/erp/projects/${current.id}?tab=tasks&section=tasks`)
    await action(member, row(member, title), '登记工时')
    await dialog(member).getByLabel('日期', { exact: true }).fill(cutoff)
    await dialog(member).getByLabel('工时', { exact: true }).fill('1')
    await reason(member, '跨期漏记设计一小时')
    await submit(member, `business/tasks/${task.id}/time/`, 409)
    await expect(dialog(member).getByRole('alert')).toContainText(`业务已锁账至 ${cutoff}`)
    expect((await api(page, `business/time/?task=${task.id}`)).count).toBe(0)
    await action(page, row(page, company.name), '锁账与重开')
    await dialog(page).getByLabel('锁账截止日期', { exact: true }).fill('')
    await dialog(page).getByLabel('锁账或重开原因', { exact: true }).fill(`重开补录验收${suffix}`)
    await submit(page, `core/company/${company.id}/period-lock/`)
    expect((await api(page, 'core/company/')).results[0]).toMatchObject({ locked_through: null, period_revision: company.period_revision + 2 })
    await submit(member, `business/tasks/${task.id}/time/`)
    const times = await api(page, `business/time/?task=${task.id}`)
    expect(times.count).toBe(1)
    expect(times.results[0]).toMatchObject({ task: task.id, user: person.id, date: cutoff, hours: '1.00', reason: '跨期漏记设计一小时' })
    const audits = (await api(page, 'core/audit/?page_size=100')).results
    expect(audits).toEqual(expect.arrayContaining([
      expect.objectContaining({ actor: admin.id, operation: 'period.lock', detail: expect.objectContaining({ after: cutoff, reason: `锁账验收${suffix}` }) }),
      expect.objectContaining({ actor: admin.id, operation: 'period.lock', detail: expect.objectContaining({ before: cutoff, after: null, reason: `重开补录验收${suffix}` }) }),
    ]))
    await page.screenshot({ path: info.outputPath('period-reopened.png'), animations: 'disabled' })
  } finally {
    const latest = (await api(page, 'core/company/')).results[0]
    if (latest.locked_through !== company.locked_through) {
      await api(page, `core/company/${company.id}/period-lock/`, {
        locked_through: company.locked_through, expected_revision: latest.period_revision,
        reason: `恢复验收前锁账设置${suffix}`,
      })
    }
  }
})
