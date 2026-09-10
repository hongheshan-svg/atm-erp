import { test, expect, observePage, login } from './fixtures'
import { selectRoles } from './role-helpers'

test('总经理单独授权后查看筛选报表，撤销后接口和入口均拒绝', async ({ page, browser }, info) => {
  const name = 'reportgm' + Date.now()
  const password = 'Report-QA-2026-only'
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/settings')
  await page.getByRole('button', { name: '新增用户', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('用户名', { exact: true }).fill(name)
  await dialog.getByLabel('姓名', { exact: true }).fill('总经理报表验收')
  await selectRoles(dialog, ['manager'])
  await dialog.getByLabel('密码', { exact: true }).fill(password)
  await dialog.getByLabel('总经理报表权限（仅项目经理角色）', { exact: true }).check()
  const created = page.waitForResponse(r => r.url().endsWith('/auth/users/') && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  const result = await created
  expect(result.status()).toBe(201)
  const account = await result.json()
  await expect(dialog).not.toBeVisible()
  const context = await browser.newContext({ baseURL: info.project.use.baseURL, viewport: info.project.use.viewport, isMobile: info.project.use.isMobile, hasTouch: info.project.use.hasTouch })
  const errors: string[] = []
  try {
    const gm = await context.newPage()
    observePage(gm, errors)
    await login(gm, name, password)
    if (await gm.getByRole('button', { name: '菜单', exact: true }).isVisible()) await gm.getByRole('button', { name: '菜单', exact: true }).click()
    await gm.getByRole('navigation').getByRole('link', { name: '经营报表', exact: true }).click()
    await expect(gm.getByRole('region', { name: '项目经营明细', exact: true })).toBeVisible()
    await gm.screenshot({ path: info.outputPath('management-report.png'), fullPage: true, animations: 'disabled' })
    await gm.getByLabel('搜索项目', { exact: true }).fill('不存在的项目' + name)
    const filtered = gm.waitForResponse(r => r.url().includes('/business/reports/') && r.request().method() === 'GET')
    await gm.getByRole('button', { name: '查询', exact: true }).click()
    expect((await (await filtered).json()).count).toBe(0)
    await expect(gm.getByText('没有符合筛选条件的项目', { exact: true })).toBeVisible()
    // User list is paginated; navigate to the created account's page through the UI.
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    const users = await page.request.get('/api/auth/users/', { headers: { Authorization: `Bearer ${token}` } })
    const count = (await users.json()).count
    const userPanel = page.getByRole('region', { name: '用户管理', exact: true })
    const lastPage = Math.ceil(count / Number(await userPanel.getByLabel('每页显示条目', { exact: true }).inputValue()))
    if (lastPage > 1) {
      const pager = userPanel.locator('.el-pagination')
      await pager.getByText(String(lastPage), { exact: true }).click()
    }
    const row = userPanel.locator('.el-table__body tr').filter({ hasText: name })
    await row.getByRole('button', { name: '操作 ▾', exact: true }).click()
    await page.getByRole('menuitem', { name: '编辑', exact: true }).click()
    await dialog.getByLabel('总经理报表权限（仅项目经理角色）', { exact: true }).uncheck()
    const revoked = page.waitForResponse(r => r.url().endsWith(`/auth/users/${account.id}/`) && r.request().method() === 'PATCH')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    expect((await revoked).status()).toBe(200)
    const gmToken = await gm.evaluate(() => localStorage.getItem('access_token'))
    expect((await gm.request.get('/api/business/reports/', { headers: { Authorization: `Bearer ${gmToken}` } })).status()).toBe(403)
    await gm.reload()
    await expect(gm).toHaveURL(/workbench/)
    await expect(gm.getByRole('navigation').getByRole('link', { name: '经营报表', exact: true })).toHaveCount(0)
  } finally { await context.close() }
  expect(errors).toEqual([])
})
