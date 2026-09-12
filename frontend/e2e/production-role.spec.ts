import type { Browser, BrowserContext, TestInfo } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { test, expect, login, observePage, expectHttpError, type Page, type Locator } from './fixtures'
import { selectRoles } from './role-helpers'

const password = 'Production-role-QA-2026-only'
const contexts: BrowserContext[] = []
const errors: string[] = []
const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, title: string) => page.locator('.el-table__body tr:visible').filter({ hasText: title })
const date = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
async function api(page: Page, path: string, data?: Record<string, unknown>, status = 200) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() }
  const response = data === undefined
    ? await page.request.get('/api/' + path, { headers })
    : await page.request.post('/api/' + path, { headers, data })
  expect(response.status(), await response.text()).toBe(status)
  return response.json()
}
async function save(page: Page, path: string, status = 200) {
  if (status >= 400) expectHttpError(page, '/api/' + path, status)
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/' + path && response.request().method() === 'POST')
  await dialog(page).getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(status)
  if (status < 300) await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  return response.json()
}
async function action(page: Page, target: Locator, name: string) {
  await target.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(page)).toBeVisible()
}
async function reason(page: Page, text: string) {
  await dialog(page).getByLabel('原因 / 说明', { exact: true }).fill(text)
}
async function session(browser: Browser, info: TestInfo, username: string) {
  const context = await browser.newContext({ baseURL: info.project.use.baseURL, viewport: info.project.use.viewport, isMobile: info.project.use.isMobile, hasTouch: info.project.use.hasTouch })
  contexts.push(context)
  const page = await context.newPage()
  observePage(page, errors)
  await login(page, username, password)
  return page
}

test.beforeEach(async ({ page }) => {
  errors.length = 0
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
})
test.afterEach(async () => {
  for (const context of contexts.splice(0)) await context.close()
  expect(errors, '生产经理与项目经理页面不应出现未预期异常').toEqual([])
})

test('生产经理完成参与项目派工、团队工时纠错、安装与保内售后，设计及外部项目权限隔离', async ({ page: admin, browser }, info) => {
  test.setTimeout(240000)
  const suffix = String(Date.now())
  // Only two projects are created. All fixtures use authenticated APIs or forms;
  // no existing business record, installation setting or database is rewritten.
  await admin.goto('/erp/settings?section=users')
  await admin.getByRole('button', { name: '新增用户', exact: true }).click()
  await expect(dialog(admin).getByRole('group', { name: '角色', exact: true }).getByRole('checkbox')).toHaveCount(11)
  await dialog(admin).getByLabel('用户名', { exact: true }).fill(`production_${suffix}`)
  await dialog(admin).getByLabel('姓名', { exact: true }).fill(`生产经理${suffix}`)
  await selectRoles(dialog(admin), ['production_manager'])
  await dialog(admin).getByLabel('密码', { exact: true }).fill(password)
  const producer = await save(admin, 'auth/users/', 201)
  expect(producer.roles).toEqual(['production_manager'])
  async function supportingAccount(role: string, label: string) {
    return api(admin, 'auth/users/', { username: `${label}_${suffix}`, display_name: `${label}${suffix}`, roles: [role], password, hourly_cost: '25.00' }, 201)
  }
  const owner = await supportingAccount('manager', 'production_owner')
  const first = await supportingAccount('member', 'production_member_a')
  const second = await supportingAccount('member', 'production_member_b')
  const customer = await api(admin, 'business/partners/', { name: `生产验收客户${suffix}`, kind: 'customer' }, 201)
  const manager = await session(browser, info, owner.username)
  await manager.goto('/erp/projects')
  await manager.getByRole('button', { name: '新建项目', exact: true }).click()
  await dialog(manager).getByLabel('项目名称', { exact: true }).fill(`生产交付验收${suffix}`)
  await dialog(manager).getByLabel('客户', { exact: true }).selectOption(String(customer.id))
  await dialog(manager).getByLabel('负责人', { exact: true }).selectOption(String(owner.id))
  await dialog(manager).getByLabel('项目成员', { exact: true }).selectOption([producer.id, first.id, second.id].map(String))
  await dialog(manager).getByLabel('质保月数', { exact: true }).fill('12')
  const current = await save(manager, 'business/projects/', 201)
  expect((await api(manager, `business/projects/${current.id}/`)).members).toEqual(expect.arrayContaining([producer.id, first.id, second.id]))
  const outside = await api(admin, 'business/projects/', { name: `其他生产项目${suffix}`, customer: customer.id, manager: owner.id, members: [first.id] }, 201)
  const outsideTask = await api(admin, 'business/tasks/', { project: outside.id, kind: 'assembly', title: `外部装配${suffix}`, assignee: first.id }, 201)
  const design = await api(manager, 'business/tasks/', { project: current.id, kind: 'design', title: `已完成设计${suffix}`, assignee: first.id }, 201)
  await api(manager, `business/tasks/${design.id}/complete/`, { reason: '图纸审核完成，转生产执行' })
  const designBefore = await api(admin, `business/tasks/${design.id}/`)
  const outsideBefore = await api(admin, `business/tasks/${outsideTask.id}/`)
  const page = await session(browser, info, producer.username)
  expect((await api(page, 'auth/me/')).roles).toEqual(['production_manager'])
  expect((await api(page, 'business/projects/')).results.map((project: { id: number }) => project.id)).toEqual([current.id])
  expect(await api(page, `business/projects/${current.id}/`)).toMatchObject({ can_manage: false, can_edit_bom: false, can_manage_production: true })
  const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
  await expect(nav.getByRole('link', { name: '项目', exact: true, includeHidden: true })).toHaveCount(1)
  for (const name of ['销售', '采购', '库存', '收付款', '经营报表']) await expect(nav.getByRole('link', { name, exact: true, includeHidden: true })).toHaveCount(0)
  await expect(nav.getByRole('link', { name: '设置', exact: true, includeHidden: true })).toHaveCount(1)
  await api(page, 'auth/users/', undefined, 403)
  await page.goto('/erp/settings?section=account')
  await expect(page.getByRole('button', { name: '修改密码', exact: true })).toBeVisible()
  for (const name of ['用户管理', '公司资料', '编号规则', '操作审计']) await expect(page.getByRole('tab', { name, exact: true })).toHaveCount(0)
  await api(page, `business/projects/${outside.id}/`, undefined, 404)
  for (const path of ['business/purchases/', 'business/entries/', 'business/reports/', `business/projects/${current.id}/cost/`]) await api(page, path, undefined, 403)
  await api(page, 'business/tasks/', { project: current.id, kind: 'design', title: '禁止生产经理创建设计', assignee: first.id }, 403)
  await api(page, `business/tasks/${design.id}/assign/`, { assignee: second.id, reason: '不能代替设计负责人派工' }, 403)
  await api(page, `business/tasks/${design.id}/reopen/`, { reason: '生产角色不能重开设计' }, 403)
  await api(page, `business/tasks/${design.id}/time/`, { user: first.id, date: date(), hours: '1', reason: '不能登记设计团队工时' }, 403)
  await api(page, 'business/tasks/', { project: outside.id, kind: 'assembly', title: '禁止跨项目派工', assignee: first.id }, 403)
  await api(page, `business/tasks/${outsideTask.id}/assign/`, { assignee: second.id, reason: '禁止跨项目重新派工' }, 404)
  expect(await api(admin, `business/tasks/${design.id}/`)).toEqual(designBefore)
  expect(await api(admin, `business/tasks/${outsideTask.id}/`)).toEqual(outsideBefore)
  expect((await api(admin, `business/time/?task=${design.id}`)).count).toBe(0)
  expect((await api(admin, `business/tasks/?project=${outside.id}`)).count).toBe(1)
  expect((await api(admin, `business/tasks/?project=${current.id}`)).count).toBe(1)

  await page.goto(`/erp/projects/${current.id}?tab=tasks&section=tasks`)
  await expect(page.getByRole('button', { name: '项目操作 ▾', exact: true })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: '成本与预算', exact: true })).toHaveCount(0)
  await expect(row(page, designBefore.title).getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  async function createTask(kind: string, title: string) {
    await page.getByRole('button', { name: '新建任务', exact: true }).click()
    await expect(dialog(page).getByLabel('阶段', { exact: true }).locator('option[value="design"]')).toHaveCount(0)
    await expect(dialog(page).getByLabel('项目', { exact: true }).locator(`option[value="${outside.id}"]`)).toHaveCount(0)
    await dialog(page).getByLabel('阶段', { exact: true }).selectOption(kind)
    await dialog(page).getByLabel('任务名称', { exact: true }).fill(title)
    await dialog(page).getByLabel('执行人', { exact: true }).selectOption(String(first.id))
    await dialog(page).getByLabel('期限', { exact: true }).fill(date())
    return save(page, 'business/tasks/', 201)
  }
  const assemblyTitle = `装配派工${suffix}`, testTitle = `调试派工${suffix}`
  const assembly = await createTask('assembly', assemblyTitle)
  const commissioning = await createTask('test', testTitle)
  await action(page, row(page, testTitle), '完成任务')
  await reason(page, '装配未完成时不应提前完成调试')
  await save(page, `business/tasks/${commissioning.id}/complete/`, 409)
  await expect(dialog(page).getByRole('alert')).toContainText('装配')
  expect((await api(admin, `business/tasks/${commissioning.id}/`)).status).toBe('open')
  await dialog(page).getByRole('button', { name: '取消', exact: true }).click()
  await action(page, row(page, assemblyTitle), '取消任务')
  await reason(page, '排程暂缓后恢复同一任务')
  await save(page, `business/tasks/${assembly.id}/cancel/`)
  await expect(row(page, assemblyTitle)).toContainText('已取消')
  await action(page, row(page, assemblyTitle), '重开任务')
  await reason(page, '排程恢复')
  await save(page, `business/tasks/${assembly.id}/reopen/`)
  await page.goto('/erp/workbench')
  const work = await api(page, 'business/workbench/?page_size=5')
  expect(work.tasks.count).toBe(0)
  expect(work.production_tasks.results.map((task: { id: number }) => task.id)).toEqual(expect.arrayContaining([assembly.id, commissioning.id]))
  expect(work.production_tasks.results.map((task: { id: number }) => task.id)).not.toContain(outsideTask.id)
  const queue = page.getByRole('region', { name: '生产与售后派工', exact: true })
  await expect(queue).toBeVisible()
  await queue.getByRole('link').filter({ hasText: assemblyTitle }).click()
  await expect(page).toHaveURL(new RegExp(`/erp/projects/${current.id}\\?.*focus=${assembly.id}`))
  await expect(dialog(page).getByLabel('任务', { exact: true })).toHaveValue(assemblyTitle)
  await dialog(page).getByRole('button', { name: '重新分配', exact: true }).click()
  await dialog(page).getByLabel('执行人', { exact: true }).selectOption(String(second.id))
  await reason(page, '生产经理将装配交接给第二名成员')
  await save(page, `business/tasks/${assembly.id}/assign/`)
  expect(await api(admin, `business/tasks/${assembly.id}/`)).toMatchObject({ assignee: second.id, status: 'open' })
  await action(page, row(page, assemblyTitle), '登记工时')
  await dialog(page).getByLabel('人员', { exact: true }).selectOption(String(second.id))
  await dialog(page).getByLabel('日期', { exact: true }).fill(date())
  await dialog(page).getByLabel('工时', { exact: true }).fill('3')
  await reason(page, '团队装配工时原记录')
  const original = await save(page, `business/tasks/${assembly.id}/time/`)
  await page.getByRole('tab', { name: '工时记录', exact: true }).click()
  await action(page, row(page, '团队装配工时原记录'), '更正工时')
  await dialog(page).getByLabel('更正后工时', { exact: true }).fill('2')
  await reason(page, '核对后团队实际装配两小时')
  const replacement = await save(page, `business/time/${original.id}/amend/`)
  const times = (await api(page, `business/time/?task=${assembly.id}`)).results
  expect(times).toHaveLength(3)
  expect(times).toEqual(expect.arrayContaining([
    expect.objectContaining({ id: original.id, user: second.id, hours: '3.00' }),
    expect.objectContaining({ reversal_of: original.id, hours: '-3.00' }),
    expect.objectContaining({ id: replacement.id, correction_of: original.id, hours: '2.00' }),
  ]))
  for (const time of times) {
    expect(time).not.toHaveProperty('cost')
    expect(time).not.toHaveProperty('hourly_cost')
  }
  await expect(row(page, '团队装配工时原记录')).toContainText('已冲销')
  await expect(row(page, '团队装配工时原记录').getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('production-team-time-correction.png'), fullPage: true, animations: 'disabled' })
  await page.getByRole('tab', { name: '项目任务', exact: true }).click()
  async function complete(title: string, id: number) {
    await action(page, row(page, title), '完成任务')
    await reason(page, '生产经理核对现场执行完成')
    await save(page, `business/tasks/${id}/complete/`)
    expect((await api(admin, `business/tasks/${id}/`)).status).toBe('done')
  }
  await complete(assemblyTitle, assembly.id)
  await complete(testTitle, commissioning.id)

  // Physical stock and shipment are separate jobs: API fixtures act as admin / PM,
  // while production manager handles the installation generated by shipment.
  const item = await api(admin, 'business/items/', { name: `装配领料${suffix}` }, 201)
  const demand = await api(manager, `business/projects/${current.id}/demand/`)
  await api(manager, `business/projects/${current.id}/revise-bom/`, { expected_revision: demand.revision, lines: [{ item: item.id, quantity: '1', assembly_unit: '整机', change_note: '交付配套物料' }] })
  await api(admin, 'business/stocks/opening/', { item: item.id, quantity: '1', unit_cost: '10', reason: '隔离生产验收期初物料' })
  const stock = (await api(admin, `business/stocks/?item=${item.id}`)).results[0]
  await api(admin, 'business/stocks/issue/', { project: current.id, stock: stock.id, quantity: '1', reason: '独立仓管领料步骤' })
  const delivery = await api(manager, `business/projects/${current.id}/ship/`, { quantity: 1, date: date(), installer: first.id, acceptor: owner.id })
  const installation = (await api(admin, `business/tasks/?project=${current.id}&kind=install`)).results[0]
  await page.reload()
  await action(page, row(page, installation.title), '重新分配')
  await dialog(page).getByLabel('执行人', { exact: true }).selectOption(String(second.id))
  await reason(page, '安装排班交给第二名成员')
  await save(page, `business/tasks/${installation.id}/assign/`)
  await complete(installation.title, installation.id)
  await api(manager, `business/deliveries/${delivery.id}/accept/`, { date: date(), reason: '项目经理完成客户现场验收' })
  expect((await api(manager, `business/projects/${current.id}/`)).status).toBe('warranty')
  const entriesBefore = await api(admin, `business/entries/?project=${current.id}`)
  const tasksBefore = (await api(admin, `business/tasks/?project=${current.id}`)).count
  await api(page, `business/projects/${current.id}/service/`, { delivery: delivery.id, date: date(), title: '禁止生产经理确认收费', assignee: first.id, fee: '100' }, 403)
  expect((await api(admin, `business/tasks/?project=${current.id}`)).count).toBe(tasksBefore)
  expect(await api(admin, `business/entries/?project=${current.id}`)).toEqual(entriesBefore)
  await page.reload()
  await page.getByRole('button', { name: '项目操作 ▾', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: '结项', exact: true })).toHaveCount(0)
  await page.getByRole('menuitem', { name: '登记售后', exact: true }).click()
  await expect(dialog(page).getByRole('alert')).toContainText('质保内免费')
  await expect(dialog(page).getByLabel('收费金额（元）', { exact: true })).toHaveCount(0)
  await dialog(page).getByLabel('交付批次', { exact: true }).selectOption(String(delivery.id))
  await dialog(page).getByLabel('日期', { exact: true }).fill(date())
  const serviceTitle = `保内传感器复核${suffix}`
  await dialog(page).getByLabel('售后事项', { exact: true }).fill(serviceTitle)
  await dialog(page).getByLabel('执行人', { exact: true }).selectOption(String(first.id))
  const service = await save(page, `business/projects/${current.id}/service/`)
  await page.getByRole('tab', { name: '交付与售后', exact: true }).click()
  await page.getByRole('tab', { name: '售后任务', exact: true }).click()
  await action(page, row(page, serviceTitle), '重新分配')
  await dialog(page).getByLabel('执行人', { exact: true }).selectOption(String(second.id))
  await reason(page, '售后由现场熟悉设备的成员处理')
  await save(page, `business/tasks/${service.id}/assign/`)
  await complete(serviceTitle, service.id)
  expect((await api(admin, `business/tasks/${service.id}/`)).assignee).toBe(second.id)
  expect(await api(admin, `business/entries/?project=${current.id}`)).toEqual(entriesBefore)
  await page.screenshot({ path: info.outputPath('production-warranty-service.png'), fullPage: true, animations: 'disabled' })

  await page.getByRole('tab', { name: '附件', exact: true }).click()
  await page.getByRole('button', { name: '上传附件', exact: true }).click()
  const categories = dialog(page).getByLabel('分类', { exact: true })
  await expect(categories.locator('option[value="contract"],option[value="receipt"]')).toHaveCount(0)
  await categories.selectOption('drawing')
  const filename = `生产装配指导-${suffix}.txt`, content = '生产装配与现场调试指导，技术版本 A。'
  await dialog(page).getByLabel('文件', { exact: true }).setInputFiles({ name: filename, mimeType: 'text/plain', buffer: Buffer.from(content) })
  const document = await save(page, 'business/documents/', 201)
  await row(page, filename).getByRole('button', { name: '操作 ▾', exact: true }).click()
  const downloading = page.waitForEvent('download')
  await page.getByRole('menuitem', { name: '下载', exact: true }).click()
  const download = await downloading
  const output = info.outputPath(filename)
  await download.saveAs(output)
  expect(await readFile(output, 'utf8')).toBe(content)
  expect((await page.request.get(`/api/business/documents/${document.id}/download/`)).status()).toBe(403)
  await page.screenshot({ path: info.outputPath('production-technical-document.png'), fullPage: true, animations: 'disabled' })
  await info.attach('production-manager-chain', { body: JSON.stringify({ producer: producer.id, project: current.id, outside: outside.id, assembly: assembly.id, commissioning: commissioning.id, originalTime: original.id, replacementTime: replacement.id, delivery: delivery.id, installation: installation.id, service: service.id, document: document.id, netHours: 2, newServiceReceivables: 0 }), contentType: 'application/json' })
})
