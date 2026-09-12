import type { Browser, BrowserContext, TestInfo } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { test, expect, login, observePage, expectHttpError, type Page, type Locator } from './fixtures'
import { selectRoles } from './role-helpers'

const password = 'Specialist-role-QA-2026-only'
const contexts: BrowserContext[] = []
const errors: string[] = []
const d = (page: Page) => page.getByRole('dialog')
const row = (page: Page, text: string) => page.locator('.el-table__body tr:visible').filter({ hasText: text }).first()
const date = () => new Date().toISOString().slice(0, 10)
async function api(page: Page, path: string, data?: Record<string, unknown>, status = 200) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() }
  const response = data === undefined ? await page.request.get('/api/' + path, { headers }) : await page.request.post('/api/' + path, { headers, data })
  expect(response.status(), await response.text()).toBe(status)
  return response.json()
}
async function save(page: Page, path: string, status = 200) {
  if (status >= 400) expectHttpError(page, '/api/' + path, status)
  const pending = page.waitForResponse(r => new URL(r.url()).pathname === '/api/' + path && ['POST', 'PATCH'].includes(r.request().method()))
  await d(page).getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(status)
  if (status < 300) await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  return response.json()
}
async function action(page: Page, target: Locator, name: string) {
  await target.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(d(page)).toBeVisible()
}
async function account(page: Page, role: string, label: string, suffix: string) {
  await page.goto('/erp/settings?section=users')
  await page.getByRole('button', { name: '新增用户', exact: true }).click()
  await expect(d(page).getByRole('group', { name: '角色', exact: true }).getByRole('checkbox')).toHaveCount(11)
  await d(page).getByLabel('用户名', { exact: true }).fill(`${role}_${suffix}`)
  await d(page).getByLabel('姓名', { exact: true }).fill(label + suffix)
  await selectRoles(d(page), [role])
  await d(page).getByLabel('密码', { exact: true }).fill(password)
  const person = await save(page, 'auth/users/', 201)
  expect(person.roles).toEqual([role])
  return person
}
async function session(browser: Browser, info: TestInfo, username: string) {
  const context = await browser.newContext({ baseURL: info.project.use.baseURL, viewport: info.project.use.viewport, isMobile: info.project.use.isMobile, hasTouch: info.project.use.hasTouch })
  contexts.push(context)
  const page = await context.newPage()
  observePage(page, errors)
  await login(page, username, password)
  return page
}
async function project(admin: Page, name: string, members: number[] = []) {
  const me = await api(admin, 'auth/me/')
  const customer = await api(admin, 'business/partners/', { name: '客户' + name, kind: 'customer' }, 201)
  return api(admin, 'business/projects/', { name, customer: customer.id, manager: me.id, members }, 201)
}
test.beforeEach(async ({ page }) => {
  errors.length = 0
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
})
test.afterEach(async () => {
  for (const context of contexts.splice(0)) await context.close()
  expect(errors).toEqual([])
})

for (const [role, label, category] of [
  ['mechanical_engineer', '机械工程师', 'drawing'],
  ['electrical_engineer', '电气工程师', 'other'],
]) {
  test(`${label}维护参与项目BOM和技术附件、完成本人任务，管理与金额权限隔离`, async ({ page: admin, browser }, info) => {
    const suffix = String(Date.now())
    const person = await account(admin, role, label, suffix)
    const current = await project(admin, label + '设计验收' + suffix, [person.id])
    const outside = await project(admin, '其他项目' + suffix)
    const task = await api(admin, 'business/tasks/', { project: current.id, kind: 'design', title: label + '设计任务' + suffix, assignee: person.id }, 201)
    const page = await session(browser, info, person.username)
    expect((await api(page, 'auth/me/')).roles).toEqual([role])
    const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
    for (const title of ['项目', 'BOM', '基础资料']) await expect(nav.getByRole('link', { name: title, exact: true, includeHidden: true })).toHaveCount(1)
    for (const title of ['销售', '采购', '库存', '收付款', '经营报表']) await expect(nav.getByRole('link', { name: title, exact: true, includeHidden: true })).toHaveCount(0)
    const projects = await api(page, 'business/projects/')
    expect(projects.results.map((p: { id: number }) => p.id)).toEqual([current.id])
    await api(page, `business/projects/${outside.id}/`, undefined, 404)
    for (const path of ['business/purchases/', 'business/entries/', 'business/reports/', `business/projects/${current.id}/cost/`]) await api(page, path, undefined, 403)
    await page.goto('/erp/masterdata?section=items')
    await page.getByRole('button', { name: '新增物料', exact: true }).click()
    const code = `ENG-${suffix}`
    await d(page).getByLabel('物料名称', { exact: true }).fill(label + '设计物料' + suffix)
    await d(page).getByLabel('物料编码（留空自动生成）', { exact: true }).fill(code)
    const item = await save(page, 'business/items/', 201)
    await page.goto(`/erp/projects/${current.id}?tab=bom`)
    await expect(page.getByRole('button', { name: '项目操作 ▾', exact: true })).toHaveCount(0)
    await expect(page.getByRole('tab', { name: '成本与预算', exact: true })).toHaveCount(0)
    const demand = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
    await demand.locator('input[type=file]').setInputFiles({ name: 'engineering-bom.csv', mimeType: 'text/csv', buffer: Buffer.from(`物料编码,单元,需求数量,变更说明,需求日期,申请日期,申请人\n${code},设计单元,2,初版,,,${label}\n`) })
    await demand.getByRole('button', { name: '确认导入', exact: true }).click()
    await save(page, `business/projects/${current.id}/revise-bom/`)
    expect((await api(page, `business/projects/${current.id}/demand/`)).lines).toEqual(expect.arrayContaining([expect.objectContaining({ item: item.id, quantity: '2.000' })]))
    await page.getByRole('tab', { name: '附件', exact: true }).click()
    await page.getByRole('button', { name: '上传附件', exact: true }).click()
    const categories = d(page).getByLabel('分类', { exact: true })
    await expect(categories.locator('option[value="contract"],option[value="receipt"]')).toHaveCount(0)
    await categories.selectOption(category)
    const filename = `${label}-${suffix}.txt`, content = `${label}项目技术资料，版本A。`
    await d(page).getByLabel('文件', { exact: true }).setInputFiles({ name: filename, mimeType: 'text/plain', buffer: Buffer.from(content) })
    const doc = await save(page, 'business/documents/', 201)
    await row(page, filename).getByRole('button', { name: '操作 ▾', exact: true }).click()
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: '下载', exact: true }).click()
    const download = await downloadEvent
    const output = info.outputPath(filename)
    await download.saveAs(output)
    expect(await readFile(output, 'utf8')).toBe(content)
    expect((await page.request.get(`/api/business/documents/${doc.id}/download/`)).status()).toBe(403)
    await page.screenshot({ path: info.outputPath(`${role}-documents.png`), fullPage: true, animations: 'disabled' })
    await page.getByRole('tab', { name: '任务与工时', exact: true }).click()
    await action(page, row(page, label + '设计任务' + suffix), '完成任务')
    await d(page).getByLabel('原因 / 说明', { exact: true }).fill('设计资料已交付')
    await save(page, `business/tasks/${task.id}/complete/`)
    await action(page, row(page, label + '设计任务' + suffix), '登记工时')
    await d(page).getByLabel('工时', { exact: true }).fill('2')
    await d(page).getByLabel('原因 / 说明', { exact: true }).fill('设计与复核')
    await save(page, `business/tasks/${task.id}/time/`)
    const times = await api(page, `business/time/?task=${task.id}`)
    expect(times.results).toHaveLength(1)
    expect(times.results[0]).toMatchObject({ user: person.id, hours: '2.00' })
    expect(times.results[0]).not.toHaveProperty('cost')
    await page.screenshot({ path: info.outputPath(`${role}-tasks.png`), fullPage: true, animations: 'disabled' })
  })
}

test('采购经理从工作台审核采购与超预算摘要，本人申请仍不可自批', async ({ page: admin, browser }, info) => {
  const suffix = String(Date.now())
  const person = await account(admin, 'purchase_manager', '采购经理', suffix)
  const buyer = await account(admin, 'purchaser', '采购员', suffix)
  const current = await project(admin, '采购审核验收' + suffix)
  await api(admin, `business/projects/${current.id}/budget/`, { materials: '100', labor: '777', expenses: '888', expected_revision: 0, reason: '设置独立材料额度' })
  const item = await api(admin, 'business/items/', { name: '审核物料' + suffix }, 201)
  const supplier = await api(admin, 'business/partners/', { name: '审核供应商' + suffix, kind: 'supplier' }, 201)
  const applicant = await session(browser, info, buyer.username)
  const page = await session(browser, info, person.username)
  const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
  for (const title of ['采购', '项目', '基础资料']) await expect(nav.getByRole('link', { name: title, exact: true, includeHidden: true })).toHaveCount(1)
  for (const title of ['销售', '收付款', '经营报表']) await expect(nav.getByRole('link', { name: title, exact: true, includeHidden: true })).toHaveCount(0)
  expect(await api(page, `business/projects/${current.id}/`)).toMatchObject({ can_manage: false, can_edit_bom: false })
  for (const path of ['business/entries/', 'business/reports/', `business/projects/${current.id}/cost/`]) await api(page, path, undefined, 403)
  async function order(actor: Page, price: string) {
    await actor.goto('/erp/purchases')
    await actor.getByRole('button', { name: '新建采购', exact: true }).click()
    for (const [label, value] of [['项目', current.id], ['供应商', supplier.id], ['物料', item.id]]) await d(actor).getByLabel(String(label), { exact: true }).selectOption(String(value))
    await d(actor).getByLabel('交期', { exact: true }).fill(date())
    await d(actor).getByLabel('数量', { exact: true }).fill('1')
    await d(actor).getByLabel('含税单价（元）', { exact: true }).fill(price)
    const created = await save(actor, 'business/purchases/', 201)
    const purchase = await api(actor, `business/purchases/${created.id}/`)
    await action(actor, row(actor, purchase.code), '提交采购')
    await save(actor, `business/purchases/${created.id}/submit/`)
    return purchase
  }
  const first = await order(applicant, '10')
  await page.goto('/erp/workbench')
  const approvals = page.getByRole('region', { name: '待批准采购', exact: true })
  await expect(approvals).toBeVisible()
  const pages = Math.ceil((await api(page, 'business/workbench/?page_size=5')).approvals.count / 5)
  for (let index = 1; index < pages && !await approvals.getByRole('link').filter({ hasText: first.code }).count(); index++) {
    await approvals.getByRole('button', { name: '下一页', exact: true }).click()
    await expect(approvals.getByRole('status')).toContainText(`第 ${index + 1} 页`)
  }
  await approvals.getByRole('link').filter({ hasText: first.code }).click()
  await d(page).getByRole('button', { name: '批准采购', exact: true }).click()
  await expect(d(page).getByRole('alert')).toContainText('材料')
  await expect(d(page).getByRole('alert')).not.toContainText('777')
  await expect(d(page).getByRole('alert')).not.toContainText('888')
  await save(page, `business/purchases/${first.id}/approve/`)
  const second = await order(applicant, '200')
  await page.goto('/erp/purchases')
  await action(page, row(page, second.code), '批准采购')
  await expect(d(page).getByRole('heading', { name: '超预算采购审批', exact: true })).toBeVisible()
  await d(page).getByLabel('超预算批准原因', { exact: true }).fill('已与项目负责人核对采购追加需求')
  await d(page).getByLabel('确认承担本次超预算采购', { exact: true }).check()
  await page.screenshot({ path: info.outputPath('purchase-manager-approval.png'), animations: 'disabled' })
  await save(page, `business/purchases/${second.id}/approve-over-budget/`)
  const self = await order(page, '1')
  await action(page, row(page, self.code), '批准采购')
  await d(page).getByLabel('超预算批准原因', { exact: true }).fill('验证采购经理仍不能自行批准本人申请')
  await d(page).getByLabel('确认承担本次超预算采购', { exact: true }).check()
  await save(page, `business/purchases/${self.id}/approve-over-budget/`, 403)
  await expect(d(page).locator('.el-alert--error')).toContainText('申请人不能审批自己的单据')
  expect((await api(page, `business/purchases/${self.id}/`)).status).toBe('submitted')
  const entries = (await api(admin, `business/entries/?project=${current.id}`)).results
  expect(entries.filter((entry: { purchase: number }) => entry.purchase)).toHaveLength(2)
  await info.attach('purchase-manager-result', { body: JSON.stringify({ account: person.id, project: current.id, approved: [first.id, second.id], selfDenied: self.id, payableCount: 2 }), contentType: 'application/json' })
})
