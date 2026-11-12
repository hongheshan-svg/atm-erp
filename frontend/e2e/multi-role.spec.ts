import { test, expect, login, accountTokens, openRowAction, searchList } from './fixtures'
import { selectRoles } from './role-helpers'

test('管理员分配采购兼仓库，保存回显并即时撤销采购权限', async ({ page }, info) => {
  const username = `dual${Date.now()}`, password = 'Multi-role-QA-only-2026-password'
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  // Keep the administrator session in this API context while the page changes users.
  const headers = { Authorization: `Bearer ${(await accountTokens(page.request, 'admin', process.env.E2E_ADMIN_PASSWORD!)).access}` }
  await page.goto('/erp/settings?section=users')
  await page.getByRole('button', { name: '新增用户', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('用户名', { exact: true }).fill(username)
  await dialog.getByLabel('姓名', { exact: true }).fill('采购兼仓库')
  await selectRoles(dialog, ['purchaser', 'warehouse'])
  await expect(dialog.getByRole('status')).toContainText('新增：采购员、仓管')
  await dialog.getByLabel('密码', { exact: true }).fill(password)
  const created = page.waitForResponse(r => r.url().endsWith('/auth/users/') && r.request().method() === 'POST')
  await dialog.locator('button[type="submit"]').click()
  const response = await created
  expect(response.status()).toBe(201)
  const account = await response.json()
  expect(account.roles.sort()).toEqual(['purchaser', 'warehouse'])
  await expect(dialog).toBeHidden()
  // 按账号搜索定位新用户，不假设它排在最后一页。
  const panel = await searchList(page, '用户管理', username)
  const row = panel.locator('.el-table__body tr').filter({ hasText: username })
  await expect(row).toHaveCount(1)
  // 手机窄屏不显示角色列，角色并在姓名格的摘要行里。
  const roles = info.project.name === 'mobile' ? row.locator('.mobile-row-summary:not(.mobile-row-links)') : row.locator('.role-tags')
  await expect(roles).toContainText('采购员')
  await expect(roles).toContainText('仓管')
  await openRowAction(page, row, '编辑')
  expect(await dialog.getByRole('group', { name: '角色', exact: true }).locator('input:checked').evaluateAll(els => els.map(el => (el as HTMLInputElement).value).sort())).toEqual(['purchaser', 'warehouse'])
  await page.screenshot({ path: info.outputPath('multiple-roles.png'), fullPage: true, animations: 'disabled' })
  await login(page, username, password)
  const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
  await expect(nav.getByRole('link', { name: '采购', exact: true, includeHidden: true })).toHaveCount(1)
  await expect(nav.getByRole('link', { name: '库存', exact: true, includeHidden: true })).toHaveCount(1)
  await expect(nav.getByRole('link', { name: '经营报表', exact: true, includeHidden: true })).toHaveCount(0)
  await page.goto('/erp/purchases')
  await expect(page.getByRole('button', { name: '新建采购', exact: true })).toBeVisible()
  const updated = await page.request.patch(`/api/auth/users/${account.id}/`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { roles: ['warehouse'] } })
  expect(updated.status(), await updated.text()).toBe(200)
  await page.reload()
  await expect(page.getByRole('button', { name: '新建采购', exact: true })).toHaveCount(0)
})
