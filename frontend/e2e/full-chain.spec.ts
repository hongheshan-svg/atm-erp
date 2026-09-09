import { test, expect, observePage, expectHttpError, type Page, type Locator } from './fixtures'
const password = 'Lean-QA-2026-password'
const day = (offset = 0) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const dialog = (p: Page) => p.getByRole('dialog')
async function fill(p: Page, label: string, value: string) {
  await dialog(p).getByLabel(label, { exact: true }).fill(value)
}
async function choose(p: Page, label: string, value: string) {
  const field = dialog(p).getByLabel(label, { exact: true })
  const option = await field.locator('option').filter({ hasText: value }).last().getAttribute('value')
  await field.selectOption(option!)
}
async function save(p: Page) {
  const response = p.waitForResponse(
    (r) => ['POST', 'PATCH'].includes(r.request().method()) && r.url().includes('/api/'),
  )
  await dialog(p).getByRole('button', { name: '保存', exact: true }).click()
  const r = await response
  expect(r.status(), await r.text()).toBeLessThan(300)
  await expect(dialog(p)).not.toBeVisible()
}
async function action(p: Page, row: Locator, name: string) {
  await row.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await p.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(p)).toBeVisible()
}
async function projectAction(p: Page, name: string) {
  await p.getByRole('button', { name: '项目操作 ▾', exact: true }).click()
  await p.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(p)).toBeVisible()
}
const row = (p: Page, text: string, region?: string) =>
  (region ? p.getByRole('region', { name: region, exact: true }) : p)
    .locator('.el-table__body tr:visible').filter({ hasText: text }).first()
async function login(p: Page, username: string, pw = password) {
  await p.goto('/erp/login')
  await p.getByLabel('用户名', { exact: true }).fill(username)
  await p.getByLabel('密码', { exact: true }).fill(pw)
  await p.getByRole('button', { name: '登录', exact: true }).click()
  await expect(p).toHaveURL(/workbench/)
}
async function read(p: Page, path: string) {
  const token = await p.evaluate(() => localStorage.getItem('access_token'))
  const response = await p.request.get('/api/' + path, { headers: { Authorization: `Bearer ${token}` } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}
async function reason(p: Page, text = '验收测试') {
  await fill(p, '原因 / 说明', text)
}
test('六角色完成签约采购生产分批交付售后与结算', async ({ browser, page }, info) => {
  test.setTimeout(300000)
  const adminPassword = process.env.E2E_ADMIN_PASSWORD
  expect(adminPassword, '必须显式提供隔离测试管理员密码').toBeTruthy()
  const suffix = String(Date.now()).slice(-9)
  const names = {
    item: '电机' + suffix,
    customer: '客户' + suffix,
    supplier: '供应商' + suffix,
    project: '完整交付' + suffix,
  }
  const roles = ['manager', 'purchaser', 'warehouse', 'finance', 'member']
  const people: Record<string, Page> = {}
  const errors: string[] = []
  page.setDefaultTimeout(15000)
  await login(page, 'admin', adminPassword)
  await expect(page.getByRole('navigation').getByRole('link')).toHaveCount(9)
  await page.goto('/erp/settings')
  for (const role of roles) {
    await page.getByRole('button', { name: '新增用户', exact: true }).click()
    await fill(page, '用户名', role + suffix)
    await fill(page, '姓名', role + suffix)
    await dialog(page).getByLabel('角色', { exact: true }).selectOption(role)
    await fill(page, '小时成本（元）', role === 'member' ? '50' : '0')
    await fill(page, '密码', password)
    await save(page)
    const context = await browser.newContext({
      baseURL: info.project.use.baseURL,
      viewport: info.project.use.viewport,
      isMobile: info.project.use.isMobile,
      hasTouch: info.project.use.hasTouch,
    })
    const p = await context.newPage()
    p.setDefaultTimeout(15000)
    observePage(p, errors)
    people[role] = p
    await login(p, role + suffix)
  }
  const { manager, purchaser, warehouse, finance, member } = people
  await purchaser.goto('/erp/masterdata')
  await purchaser.getByRole('button', { name: '新增物料', exact: true }).click()
  await fill(purchaser, '物料名称', names.item)
  await save(purchaser)
  for (const [kind, name] of [
    ['customer', names.customer],
    ['supplier', names.supplier],
  ]) {
    await purchaser.getByRole('button', { name: '新增往来单位', exact: true }).click()
    await fill(purchaser, '单位名称', name)
    await dialog(purchaser).getByLabel('类型', { exact: true }).selectOption(kind)
    await save(purchaser)
  }
  await manager.goto('/erp/sales')
  await manager.getByRole('button', { name: '新建销售', exact: true }).click()
  await fill(manager, '销售名称', names.project)
  await choose(manager, '客户', names.customer)
  await choose(manager, '负责人', 'manager' + suffix)
  await fill(manager, '设备数量', '2')
  await fill(manager, '质保月数', '0')
  await save(manager)
  const saleRow = row(manager, names.project)
  await action(manager, saleRow, '报价')
  await fill(manager, '报价金额（元）', '10000')
  await reason(manager)
  await save(manager)
  await action(manager, saleRow, '编辑销售')
  await fill(manager, '需求说明', '确认两台设备及交付范围')
  await reason(manager, '补充需求后重新确认报价')
  await save(manager)
  const revisedSale = (await read(manager, 'business/sales/?search=' + encodeURIComponent(names.project))).results[0]
  expect(revisedSale.status).toBe('draft')
  expect(Number(revisedSale.quote_amount)).toBe(0)
  expect(revisedSale.project).toBeNull()
  await action(manager, saleRow, '报价')
  await fill(manager, '报价金额（元）', '10000')
  await reason(manager, '重新确认')
  await save(manager)
  await action(manager, saleRow, '签约')
  await choose(manager, '项目成员', 'member' + suffix)
  await fill(manager, '日期', day(-2))
  await save(manager)
  await expect(manager.locator('.el-message')).toHaveCount(0)
  await action(manager, saleRow, '查看明细')
  await expect(dialog(manager).getByLabel('合同金额（元）', { exact: true })).toHaveValue('10000.00')
  await expect(dialog(manager).getByRole('button', { name: '保存', exact: true })).toHaveCount(0)
  await dialog(manager).getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog(manager)).not.toBeVisible()
  await manager.screenshot({ path: info.outputPath('sales-module.png'), fullPage: true, animations: 'disabled' })
  await saleRow.getByRole('link').click()
  await expect(manager).toHaveURL(/\/projects\/\d+$/)
  const id = Number(manager.url().split('/').pop())
  await manager.getByRole('tab', { name: 'BOM', exact: true }).click()
  const item = (await read(manager, 'business/items/?search=' + encodeURIComponent(names.item))).results[0]
  await manager
    .locator('input[type=file]')
    .setInputFiles({
      name: 'bom.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`物料编码,数量,变更说明\n${item.code},4,初版\n`),
    })
  await manager.getByRole('button', { name: '确认导入', exact: true }).click()
  await save(manager)
  await purchaser.goto(`/erp/projects/${id}`)
  await purchaser.getByRole('tab', { name: 'BOM', exact: true }).click()
  await purchaser.getByRole('button', { name: '按缺料采购', exact: true }).click()
  await choose(purchaser, '供应商', names.supplier)
  await fill(purchaser, '含税单价（元）', '100')
  await save(purchaser)
  let purchases = (await read(purchaser, `business/purchases/?project=${id}`)).results
  const po = purchases[0]
  await purchaser.goto('/erp/purchases')
  await action(purchaser, row(purchaser, po.code), '提交采购')
  await save(purchaser)
  await manager.goto('/erp/purchases')
  await action(manager, row(manager, po.code), '批准采购')
  await save(manager)
  await finance.goto('/erp/finance')
  await action(finance, row(finance, po.code, '应收应付与费用'), '登记收付款')
  await reason(finance)
  await save(finance)
  await action(finance, row(finance, po.code, '收付款流水'), '冲销付款')
  await reason(finance, '更正付款登记')
  await save(finance)
  const paymentRows = finance.getByRole('region', { name: '收付款流水', exact: true }).locator('.el-table__body tr:visible').filter({ hasText: po.code })
  await expect(paymentRows.filter({ hasText: '已冲销' })).toHaveCount(1)
  await expect(paymentRows.filter({ hasText: '冲销记录' })).toHaveCount(1)
  await expect(paymentRows.getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  await action(finance, row(finance, po.code, '应收应付与费用'), '登记收付款')
  await reason(finance, '重新登记付款')
  await save(finance)
  await warehouse.goto('/erp/purchases')
  await action(warehouse, row(warehouse, po.code), '查看明细')
  await expect(dialog(warehouse).getByLabel('含税单价（元）')).toHaveCount(0)
  await dialog(warehouse).getByRole('button', { name: '关闭', exact: true }).click()
  await action(warehouse, row(warehouse, po.code), '收货')
  await fill(warehouse, '数量', '3')
  await reason(warehouse)
  await save(warehouse)
  await purchaser.reload()
  await action(purchaser, row(purchaser, po.code), '取消未收余量')
  await reason(purchaser)
  await save(purchaser)
  await finance.reload()
  await action(finance, row(finance, po.code, '应收应付与费用'), '退款')
  await reason(finance)
  await save(finance)
  await purchaser.getByRole('button', { name: '新建采购', exact: true }).click()
  await choose(purchaser, '项目', names.project)
  await choose(purchaser, '供应商', names.supplier)
  await choose(purchaser, '物料', names.item)
  await fill(purchaser, '数量', '2')
  await fill(purchaser, '含税单价（元）', '100')
  await save(purchaser)
  purchases = (await read(purchaser, `business/purchases/?project=${id}`)).results
  const po2 = purchases.find((p: { id: number }) => p.id !== po.id)
  await action(purchaser, row(purchaser, po2.code), '提交采购')
  await save(purchaser)
  await manager.reload()
  await action(manager, row(manager, po2.code), '批准采购')
  await save(manager)
  await warehouse.reload()
  await action(warehouse, row(warehouse, po2.code), '收货')
  await reason(warehouse)
  await save(warehouse)
  await manager.goto(`/erp/projects/${id}`)
  for (const [kind, title] of [
    ['design', '设计'],
    ['assembly', '装配'],
    ['test', '调试'],
  ]) {
    await manager.getByRole('button', { name: '新建任务', exact: true }).click()
    await dialog(manager).getByLabel('阶段', { exact: true }).selectOption(kind)
    await fill(manager, '任务名称', title + suffix)
    await choose(manager, '执行人', 'member' + suffix)
    await save(manager)
  }
  await member.goto(`/erp/projects/${id}`)
  await expect(member.getByRole('navigation').getByRole('link')).toHaveCount(5)
  await expect(member.getByLabel('项目成本', { exact: true })).toHaveCount(0)
  expect((await read(member, 'business/projects/')).results.map((p: { id: number }) => p.id)).toEqual([id])
  const memberToken = await member.evaluate(() => localStorage.getItem('access_token'))
  for (const path of ['purchases/', 'entries/', `projects/${id}/cost/`]) {
    const denied = await member.request.get('/api/business/' + path, {
      headers: { Authorization: `Bearer ${memberToken}` },
    })
    expect(denied.status()).toBe(403)
  }
  for (const title of ['设计', '装配', '调试']) {
    await action(member, row(member, title + suffix), '完成任务')
    await reason(member)
    await save(member)
    await action(member, row(member, title + suffix), '登记工时')
    await fill(member, '工时', title === '设计' ? '3' : '1')
    await reason(member)
    await save(member)
  }
  const timeRows = member.getByRole('region', { name: '工时记录' })
  await action(member, timeRows.locator('.el-table__body tr:visible').last(), '更正工时')
  await fill(member, '更正后工时', '2')
  await reason(member, '更正设计工时')
  await save(member)
  const reversedTime = timeRows.locator('.el-table__body tr:visible').filter({ hasText: '已冲销' })
  await expect(reversedTime).toHaveCount(1)
  await expect(reversedTime.getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  await manager.reload()
  await projectAction(manager, '发货')
  await fill(manager, '日期', day(-1))
  const fail = manager.waitForResponse((r) => r.url().endsWith('/ship/') && r.request().method() === 'POST')
  expectHttpError(manager, `/api/business/projects/${id}/ship/`, 409)
  await dialog(manager).getByRole('button', { name: '保存', exact: true }).click()
  expect((await fail).status()).toBe(409)
  await expect(dialog(manager).getByRole('alert')).toContainText('领料')
  await dialog(manager).getByRole('button', { name: '取消', exact: true }).click()
  await warehouse.goto('/erp/inventory')
  await action(warehouse, row(warehouse, names.item, '现有库存'), '领料')
  await choose(warehouse, '项目', names.project)
  await fill(warehouse, '数量', '4')
  await reason(warehouse)
  await save(warehouse)
  for (let i = 0; i < 2; i++) {
    await manager.reload()
    await projectAction(manager, '发货')
    await fill(manager, '日期', day(-1))
    await choose(manager, '安装人', 'member' + suffix)
    await save(manager)
    const deliveries = (await read(manager, `business/deliveries/?project=${id}`)).results
    const delivery = deliveries[0]
    await member.reload()
    const installRow = row(member, delivery.code + ' 安装')
    await action(member, installRow, '登记工时')
    await fill(member, '工时', '1')
    await reason(member)
    await save(member)
    await action(member, installRow, '完成任务')
    await reason(member)
    await save(member)
    await manager.getByRole('tab', { name: '交付与售后', exact: true }).click()
    await action(manager, row(manager, delivery.code), '验收')
    await fill(manager, '日期', day(-1))
    await reason(manager)
    await save(manager)
  }
  const delivery = (await read(manager, `business/deliveries/?project=${id}`)).results[0]
  for (const [title, date, fee] of [
    ['免费售后', day(-1), '0'],
    ['收费售后', day(), '300'],
  ]) {
    await projectAction(manager, '登记售后')
    await choose(manager, '交付批次', delivery.code)
    await fill(manager, '日期', date)
    await fill(manager, '售后事项', title + suffix)
    await choose(manager, '执行人', 'member' + suffix)
    await fill(manager, '收费金额（元）', fee)
    await save(manager)
    if (fee === '0') {
      await warehouse.reload()
      await action(warehouse, row(warehouse, names.item, '现有库存'), '领料')
      await choose(warehouse, '项目', names.project)
      await choose(warehouse, '售后任务（生产领料留空）', title + suffix)
      await fill(warehouse, '数量', '1')
      await reason(warehouse)
      await save(warehouse)
    }
    await member.reload()
    await action(member, row(member, title + suffix), '登记工时')
    await fill(member, '工时', '1')
    await reason(member)
    await save(member)
    await action(member, row(member, title + suffix), '完成任务')
    await reason(member)
    await save(member)
  }
  await finance.reload()
  await finance.getByRole('button', { name: '登记费用', exact: true }).click()
  await choose(finance, '项目', names.project)
  await fill(finance, '费用名称', '差旅' + suffix)
  await fill(finance, '金额（元）', '50')
  await save(finance)
  await manager.reload()
  await projectAction(manager, '结项')
  await reason(manager)
  const closeFail = manager.waitForResponse(
    (r) => r.url().endsWith('/close/') && r.request().method() === 'POST',
  )
  expectHttpError(manager, `/api/business/projects/${id}/close/`, 409)
  await dialog(manager).getByRole('button', { name: '保存', exact: true }).click()
  expect((await closeFail).status()).toBe(409)
  await dialog(manager).getByRole('button', { name: '取消', exact: true }).click()
  const entries = (await read(finance, `business/entries/?project=${id}`)).results
  for (const entry of entries.filter((e: { balance: string }) => Number(e.balance) > 0)) {
    await finance.reload()
    const target = finance
      .getByRole('region', { name: '应收应付与费用' })
      .locator('.el-table__body tr:visible')
      .filter({ hasText: names.project })
      .filter({ hasText: entry.title })
      .first()
    await action(finance, target, '登记收付款')
    await reason(finance)
    await save(finance)
  }
  expect(await read(manager, `business/projects/${id}/cost/`)).toEqual({
    materials: '500.00',
    labor: '400.00',
    expenses: '50.00',
    purchase_return_variance: '0.00',
    total: '950.00',
  })
  await manager.reload()
  await projectAction(manager, '结项')
  await reason(manager)
  await save(manager)
  await expect(manager.getByText('已结项', { exact: false }).first()).toBeVisible()
  await projectAction(manager, '重新打开')
  await reason(manager)
  await save(manager)
  await expect(manager.locator('.el-message')).toHaveCount(0)
  await manager.screenshot({ path: info.outputPath('completed-chain.png'), fullPage: true })
  await manager.setViewportSize({ width: 390, height: 844 })
  await manager.screenshot({ path: info.outputPath('completed-chain-mobile.png'), fullPage: true })
  expect(errors).toEqual([])
  for (const p of Object.values(people)) await p.context().close()
})
