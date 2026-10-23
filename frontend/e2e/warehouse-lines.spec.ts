import { test, expect, login, openRowAction, type Page } from './fixtures'
import { selectRemoteOption } from './remote-select-helpers'
const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, text: string) => page.locator('.el-table__body tr:visible').filter({ hasText: text }).first()
async function api(page: Page, path: string, data?: object) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() }
  const response = data ? await page.request.post(`/api/${path}`, { headers, data }) : await page.request.get(`/api/${path}`, { headers })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}
async function search(page: Page, text: string) {
  await page.locator('input[type=search]').fill(text)
  await page.locator('form.resource-search').evaluate((form: HTMLFormElement) => form.requestSubmit())
}
async function save(page: Page, action: string) {
  const pending = page.waitForResponse(response => response.url().includes(action) && response.request().method() === 'POST')
  await dialog(page).locator('button[type=submit]').click()
  const response = await pending
  expect(response.ok(), await response.text()).toBeTruthy()
  await expect(dialog(page)).not.toBeVisible()
}
test('仓管收货及项目出库展示完整物料资料并逐条保存备注', async ({ page, browser }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const suffix = `${Date.now()}${info.project.name}`
  const admin = await api(page, 'auth/me/')
  const customer = await api(page, 'business/partners/', { kind: 'customer', name: `明细客户${suffix}` })
  const supplier = await api(page, 'business/partners/', { kind: 'supplier', name: `明细供方${suffix}` })
  let project = await api(page, 'business/projects/', { name: `明细验收${suffix}`, customer: customer.id, manager: admin.id })
  let item = await api(page, 'business/items/', { name: `坦克链安装板${suffix}`, specification: '板厚2mm', drawing_number: `A2608-01-00017-${suffix}`, drawing_revision: 'A', brand: '指定品牌', product_category: '12', part_type: 'custom', unit: 'PCS' })
  const demand = await api(page, `business/projects/${project.id}/demand/`)
  await api(page, `business/projects/${project.id}/revise-bom/`, { expected_revision: demand.revision, lines: [
    { item: item.id, quantity: '2', assembly_unit: '上料单元', change_note: '首版' },
    { item: item.id, quantity: '3', assembly_unit: '下料单元', change_note: '首版' },
  ] })
  const bom = await api(page, `business/projects/${project.id}/demand/`)
  let purchase = await api(page, 'business/purchases/', { project: project.id, supplier: supplier.id, due_date: '2026-12-31', lines: bom.lines.map((line: { bom_line: number; quantity: string }) => ({ item: item.id, bom_line: line.bom_line, quantity: line.quantity, unit_price: '10' })) })
  await api(page, `business/purchases/${purchase.id}/submit/`, {})
  await api(page, `business/purchases/${purchase.id}/approve/`, { reason: '隔离验收管理员审批例外' })
  project = await api(page, `business/projects/${project.id}/`)
  item = await api(page, `business/items/${item.id}/`)
  purchase = await api(page, `business/purchases/${purchase.id}/`)
  const warehouse = await api(page, 'auth/users/', { username: `whdetail${suffix}`, display_name: '仓管验收', roles: ['warehouse'], password: 'Warehouse-Detail-Only-2026' })
  const context = await browser.newContext({ baseURL: info.project.use.baseURL, viewport: info.project.use.viewport, isMobile: info.project.use.isMobile, hasTouch: info.project.use.hasTouch })
  const wh = await context.newPage()
  try {
    await login(wh, warehouse.username, 'Warehouse-Detail-Only-2026')
    await wh.goto('/erp/purchases'); await search(wh, purchase.code)
    await openRowAction(wh, row(wh, purchase.code), '收货')
    const table = dialog(wh).getByRole('table', { name: '本次收货明细', exact: true })
    for (const text of ['A2608-01-00017', '版本：A', '品牌：指定品牌', '有图·钣金', '上料单元', '下料单元']) await expect(table).toContainText(text)
    await expect(table.getByRole('columnheader').last()).toHaveText('备注')
    await expect(table).not.toContainText('单价')
    const upper = table.locator('tbody tr').filter({ hasText: '上料单元' })
    const lower = table.locator('tbody tr').filter({ hasText: '下料单元' })
    await upper.getByLabel('数量', { exact: true }).fill('2')
    await upper.getByLabel('备注', { exact: true }).fill('上料板外观合格')
    await lower.getByLabel('数量', { exact: true }).fill('1')
    await lower.getByLabel('不合格隔离数量', { exact: true }).fill('1')
    await lower.getByLabel('备注', { exact: true }).fill('下料板1件孔位待复检')
    await dialog(wh).getByLabel('原因 / 说明', { exact: true }).fill('送货单SH001，按实物分单元收货')
    const viewport = await wh.evaluate(() => ({ body: document.body.scrollWidth, visible: document.documentElement.clientWidth }))
    expect(viewport.body, JSON.stringify(viewport)).toBeLessThanOrEqual(viewport.visible)
    await dialog(wh).locator('.warehouse-scroll').evaluate(el => { el.scrollLeft = 0 })
    await dialog(wh).locator('.action-fields').evaluate(el => { const details = el.querySelector('.warehouse-lines')!; el.scrollTop += details.getBoundingClientRect().top - el.getBoundingClientRect().top })
    await wh.screenshot({ path: info.outputPath('receipt-details.png'), fullPage: true, animations: 'disabled' })
    if (info.project.name === 'desktop') {
      await dialog(wh).locator('.warehouse-scroll').evaluate(el => { el.scrollLeft = el.scrollWidth })
      await wh.screenshot({ path: info.outputPath('receipt-remarks.png'), fullPage: true, animations: 'disabled' })
    }
    await save(wh, '/receive/')
    const moves = await api(wh, `business/moves/?project=${project.id}&kind=receipt`)
    expect(moves.results.map((move: { remark: string }) => move.remark).sort()).toEqual(['上料板外观合格', '下料板1件孔位待复检'].sort())
    expect(moves.results.every((move: object) => !('value' in move))).toBe(true)
    const stock = (await api(wh, `business/stocks/?item=${item.id}`)).results[0]
    expect(stock.quantity).toBe('3.000')
    await wh.goto('/erp/inventory?section=stocks&project=all'); await search(wh, item.code)
    await openRowAction(wh, row(wh, item.code), '领料')
    await selectRemoteOption(dialog(wh).getByLabel('项目', { exact: true }), { id: project.id })
    const issueTable = dialog(wh).getByRole('table', { name: '本次出库明细', exact: true })
    for (const text of [project.code, '5.000', 'A2608-01-00017']) await expect(issueTable).toContainText(text)
    await issueTable.getByLabel('数量', { exact: true }).fill('1')
    await issueTable.getByLabel('备注', { exact: true }).fill('用于上料单元一号工位')
    await dialog(wh).getByLabel('原因 / 说明', { exact: true }).fill('装配领料')
    await dialog(wh).locator('.warehouse-scroll').evaluate(el => { el.scrollLeft = 0 })
    await dialog(wh).locator('.action-fields').evaluate(el => { const details = el.querySelector('.warehouse-lines')!; el.scrollTop += details.getBoundingClientRect().top - el.getBoundingClientRect().top })
    await wh.screenshot({ path: info.outputPath('issue-details.png'), fullPage: true, animations: 'disabled' })
    await save(wh, '/issue/')
    const issued = (await api(wh, `business/moves/?project=${project.id}&kind=issue`)).results[0]
    expect(issued).toMatchObject({ quantity: '-1.000', remark: '用于上料单元一号工位', reason: '装配领料' })
    expect((await api(wh, `business/stocks/${stock.id}/`)).quantity).toBe('2.000')
    await wh.goto(`/erp/inventory?section=moves&project=${project.id}`)
    await expect(wh.getByText('用于上料单元一号工位', { exact: true })).toBeVisible()
  } finally { await context.close() }
})
