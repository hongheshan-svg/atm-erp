import { test, expect, login } from './fixtures'

test('低频设置默认收起，键盘展开后加载并保留内容', async ({ page }, info) => {
  const requests: string[] = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (['/api/core/company/', '/api/core/codes/', '/api/core/audit/'].includes(path)) requests.push(path)
  })
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/auth/users/') && r.status() === 200),
    page.goto('/erp/settings'),
  ])
  await expect(page.getByRole('button', { name: '新增用户', exact: true })).toBeVisible()
  expect(requests).toEqual([])
  await page.screenshot({ path: info.outputPath('settings-collapsed.png'), fullPage: true, animations: 'disabled' })
  for (const [title, endpoint] of [['公司资料', 'company'], ['编号规则', 'codes'], ['操作审计', 'audit']]) {
    const section = page.locator('details').filter({ has: page.locator('summary', { hasText: title }) })
    const summary = section.locator('summary')
    const panel = section.getByRole('region', { name: title, exact: true })
    await expect(panel).toHaveCount(0)
    const response = page.waitForResponse(r => new URL(r.url()).pathname === `/api/core/${endpoint}/`)
    if (info.project.name === 'desktop') { await summary.focus(); await summary.press('Enter') }
    else await summary.tap()
    expect((await response).status()).toBe(200)
    await expect(panel).toBeVisible()
    if (info.project.name === 'desktop') { await summary.focus(); await summary.press('Space') }
    else await summary.tap()
    await expect(panel).not.toBeVisible()
    if (info.project.name === 'desktop') await summary.press('Enter')
    else await summary.tap()
    await expect(panel).toBeVisible()
    expect(requests.filter(path => path === `/api/core/${endpoint}/`)).toHaveLength(1)
  }
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const response = await page.request.get('/api/core/codes/', { headers: { Authorization: `Bearer ${token}` } })
  expect(response.ok()).toBeTruthy()
  const original = (await response.json()).results.find((r: { key: string }) => r.key === 'item')
  const suffix = String(Date.now()).slice(-7)
  const prefix = 'T' + suffix
  const edit = async (values: { prefix: string; date_format: string; padding: number; reset_cycle: string }) => {
    const row = page.getByRole('region', { name: '编号规则', exact: true }).locator('.el-table__body tr').filter({ hasText: '物料' })
    await row.getByRole('button', { name: '操作 ▾', exact: true }).click()
    await page.getByRole('menuitem', { name: '编辑', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('前缀', { exact: true }).fill(values.prefix)
    await dialog.getByLabel('日期格式', { exact: true }).selectOption(values.date_format || 'none')
    await dialog.getByLabel('流水位数（1–10）', { exact: true }).fill(String(values.padding))
    await dialog.getByLabel('重置周期', { exact: true }).selectOption(values.reset_cycle)
    await dialog.getByLabel('修改原因', { exact: true }).fill('隔离测试编号配置与恢复')
    if (values.prefix === prefix) await page.screenshot({ path: info.outputPath('number-rule-dialog.png'), animations: 'disabled' })
    const saved = page.waitForResponse(r => r.url().includes('/configure/') && r.request().method() === 'POST')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    expect((await saved).status()).toBe(200)
    await expect(dialog).not.toBeVisible()
  }
  await edit({ prefix, date_format: 'YYYYMMDD', padding: 4, reset_cycle: 'day' })
  try {
    await page.goto('/erp/masterdata')
    await page.getByRole('button', { name: '新增物料', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('物料名称', { exact: true }).fill('规则验证' + suffix)
    const created = page.waitForResponse(r => r.url().endsWith('/items/') && r.request().method() === 'POST')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    expect((await created).status()).toBe(201)
    await expect(dialog).not.toBeVisible()
    const row = page.getByRole('region', { name: '物料', exact: true }).locator('.el-table__body tr').filter({ hasText: '规则验证' + suffix })
    await expect(row).toContainText(new RegExp(prefix + '\\d{12,}'))
  } finally {
    await page.goto('/erp/settings')
    await page.locator('summary').filter({ hasText: '编号规则' }).click()
    await edit(original)
  }
})
