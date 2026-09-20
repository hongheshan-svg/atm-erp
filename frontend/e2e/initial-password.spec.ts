import { test, expect, login, expectHttpError } from './fixtures'

test('管理员随机或手动设置初始密码，用户登录后自行改密且错误提示为中文', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const suffix = `${info.project.name}-${Date.now()}`
  const accounts: { username: string; password: string }[] = []
  for (const mode of ['random', 'manual']) {
    await page.goto('/erp/settings?section=users')
    await page.getByRole('button', { name: '新增用户', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const username = `initial-${mode}-${suffix}`
    await dialog.getByLabel('用户名', { exact: true }).fill(username)
    await dialog.getByLabel('姓名', { exact: true }).fill('初始密码验收')
    await dialog.getByRole('button', { name: '随机生成', exact: true }).click()
    const passwordInput = dialog.getByLabel('密码', { exact: true })
    let password = await passwordInput.inputValue()
    expect(password).toMatch(/^[A-Za-z0-9_-]{20}$/)
    await expect(passwordInput).toHaveAttribute('type', 'text')
    await dialog.getByRole('button', { name: '隐藏密码', exact: true }).click()
    await expect(passwordInput).toHaveAttribute('type', 'password')
    if (mode === 'manual') { password = '1'; await passwordInput.fill(password) }
    await page.screenshot({ path: info.outputPath(`initial-${mode}.png`), fullPage: true })
    const saved = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/users/' && r.request().method() === 'POST')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    expect((await saved).status()).toBe(201)
    await expect(dialog).toBeHidden()
    accounts.push({ username, password })
  }
  for (const account of accounts) {
    await login(page, account.username, account.password)
    await page.goto('/erp/settings?section=account')
    await expect(page.getByRole('button', { name: '新增用户', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '修改密码', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('原密码', { exact: true }).fill(account.password)
    await dialog.getByLabel('新密码', { exact: true }).fill('123456')
    const stopExpecting = expectHttpError(page, '/api/auth/password/', 400)
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog.getByRole('alert')).toContainText('密码至少需要 12 个字符。')
    await expect(dialog.getByRole('alert')).toContainText('这个密码太常见了，请换一个密码。')
    await expect(dialog.getByRole('alert')).toContainText('密码不能只包含数字。')
    await expect(dialog.getByRole('alert')).not.toContainText('This password')
    stopExpecting()
    await page.screenshot({ path: info.outputPath(`chinese-errors-${account.username.includes('-manual-') ? 'manual' : 'random'}.png`), fullPage: true })
    const newPassword = 'Personal-K9!River-Change-2026'
    await dialog.getByLabel('新密码', { exact: true }).fill(newPassword)
    const changed = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/password/' && r.request().method() === 'POST')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    expect((await changed).status()).toBe(200)
    await expect(page).toHaveURL(/\/login$/)
    await login(page, account.username, newPassword)
  }
})
