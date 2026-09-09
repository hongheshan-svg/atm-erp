import { test, expect } from './fixtures'

test('低频设置默认收起，键盘展开后加载并保留内容', async ({ page }, info) => {
  const requests: string[] = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (['/api/core/company/', '/api/core/codes/', '/api/core/audit/'].includes(path)) requests.push(path)
  })
  await page.goto('/erp/login')
  await page.getByLabel('用户名', { exact: true }).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/workbench/)
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
})
