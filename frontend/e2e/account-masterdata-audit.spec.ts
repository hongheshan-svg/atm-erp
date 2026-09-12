import { test, expect, login, expectHttpError, type Page, type Locator } from './fixtures'

const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, text: string) => page.locator('.el-table__body tr:visible').filter({ hasText: text }).first()
async function api(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  return {
    get: async (path: string) => {
      const response = await page.request.get(`/api/${path}`, { headers })
      expect(response.status(), await response.text()).toBe(200)
      return response.json()
    },
    post: async (path: string, data: object) => {
      const response = await page.request.post(`/api/${path}`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
      expect(response.status(), await response.text()).toBeLessThan(300)
      return response.json()
    },
  }
}
async function save(page: Page, path: string, method: 'POST' | 'PATCH', status: number) {
  const pending = page.waitForResponse(response => response.request().method() === method && new URL(response.url()).pathname === path)
  await dialog(page).getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(status)
  await expect(dialog(page)).toBeHidden()
  return response.json()
}
async function edit(page: Page, target: Locator) {
  await target.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name: '编辑', exact: true }).click()
  await expect(dialog(page)).toBeVisible()
}
async function rejectedLogin(page: Page, username: string, password: string) {
  await page.goto('/erp/login')
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  const stopExpected = expectHttpError(page, '/api/auth/login/', 401)
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/auth/login/')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  expect((await pending).status()).toBe(401)
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page).toHaveURL(/\/erp\/login$/)
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
  stopExpected()
}

test('管理员从用户表单新增并停用专用账号，停用账号不能登录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const admin = await api(page), username = `disabled_audit_${Date.now()}`
  const password = 'Disabled-user-audit-2026-only'
  await page.goto('/erp/settings?section=users')
  await page.getByRole('button', { name: '新增用户', exact: true }).click()
  await dialog(page).getByLabel('用户名', { exact: true }).fill(username)
  await dialog(page).getByLabel('姓名', { exact: true }).fill('停用账号专项验收')
  await dialog(page).getByLabel('密码', { exact: true }).fill(password)
  await dialog(page).getByLabel('启用', { exact: true }).check()
  const created = await save(page, '/api/auth/users/', 'POST', 201)
  expect(await admin.get(`auth/users/${created.id}/`)).toMatchObject({ username, roles: ['member'], is_active: true })
  await page.getByRole('searchbox', { name: '搜索用户管理', exact: true }).fill(username)
  await page.getByRole('searchbox', { name: '搜索用户管理', exact: true }).press('Enter')
  await edit(page, row(page, username))
  await dialog(page).getByLabel('启用', { exact: true }).uncheck()
  await save(page, `/api/auth/users/${created.id}/`, 'PATCH', 200)
  expect(await admin.get(`auth/users/${created.id}/`)).toMatchObject({ id: created.id, username, is_active: false })
  await expect(row(page, username)).toContainText('停用')
  await page.screenshot({ path: info.outputPath('disabled-user.png'), fullPage: true, animations: 'disabled' })
  await rejectedLogin(page, username, password)
})

test('专用成员修改本人密码后退出，旧密码失效而新密码正常登录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const admin = await api(page), username = `password_audit_${Date.now()}`
  const oldPassword = 'Old-password-audit-2026-only', newPassword = 'New-password-audit-2026-only'
  const account = await admin.post('auth/users/', { username, display_name: '本人改密专项验收', roles: ['member'], password: oldPassword })
  await login(page, username, oldPassword)
  await page.goto('/erp/settings?section=account')
  await page.getByRole('button', { name: '修改密码', exact: true }).click()
  await dialog(page).getByLabel('原密码', { exact: true }).fill(oldPassword)
  await dialog(page).getByLabel('新密码', { exact: true }).fill(newPassword)
  await save(page, '/api/auth/password/', 'POST', 200)
  await expect(page).toHaveURL(/\/erp\/login$/)
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
  await rejectedLogin(page, username, oldPassword)
  await login(page, username, newPassword)
  const current = await api(page)
  expect(await current.get('auth/me/')).toMatchObject({ id: account.id, username, roles: ['member'] })
  await page.goto('/erp/settings?section=account')
  await expect(page.getByRole('heading', { name: '我的账户', exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('password-changed.png'), fullPage: true, animations: 'disabled' })
})

test('物料和往来单位编辑停用后退出新单选项，原采购关联继续可查', async ({ page }, info) => {
  test.setTimeout(120000)
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const admin = await api(page), suffix = `${Date.now()}-${info.project.name}`
  const me = await admin.get('auth/me/')
  const partner = await admin.post('business/partners/', { name: `停用前单位${suffix}`, kind: 'both', contact: '旧联系人' })
  const material = await admin.post('business/items/', { code: `INACTIVE-${suffix}`, name: `停用前物料${suffix}`, unit: '件', specification: '旧规格' })
  const project = await admin.post('business/projects/', { name: `资料停用验收${suffix}`, customer: partner.id, manager: me.id })
  const day = new Date().toLocaleDateString('sv-SE')
  const purchase = await admin.post('business/purchases/', { project: project.id, supplier: partner.id, due_date: day, lines: [{ item: material.id, quantity: '1', unit_price: '10' }] })
  const oldOrder = await admin.get(`business/purchases/${purchase.id}/`)

  await page.goto('/erp/masterdata?section=items')
  await page.getByRole('searchbox', { name: '搜索物料', exact: true }).fill(`INACTIVE-${suffix}`)
  await page.getByRole('searchbox', { name: '搜索物料', exact: true }).press('Enter')
  await edit(page, row(page, `INACTIVE-${suffix}`))
  await dialog(page).getByLabel('物料名称', { exact: true }).fill(`停用后物料${suffix}`)
  await dialog(page).getByLabel('规格', { exact: true }).fill('已核对的新规格')
  await dialog(page).getByLabel('启用', { exact: true }).uncheck()
  await save(page, `/api/business/items/${material.id}/`, 'PATCH', 200)
  expect(await admin.get(`business/items/${material.id}/`)).toMatchObject({ id: material.id, code: `INACTIVE-${suffix}`, name: `停用后物料${suffix}`, specification: '已核对的新规格', is_active: false })
  await expect(row(page, `INACTIVE-${suffix}`)).toContainText('停用')

  await page.goto('/erp/masterdata?section=partners')
  await page.getByRole('searchbox', { name: '搜索客户与供应商', exact: true }).fill(`停用前单位${suffix}`)
  await page.getByRole('searchbox', { name: '搜索客户与供应商', exact: true }).press('Enter')
  await edit(page, row(page, `停用前单位${suffix}`))
  await dialog(page).getByLabel('单位名称', { exact: true }).fill(`停用后单位${suffix}`)
  await dialog(page).getByLabel('联系人', { exact: true }).fill('核对后联系人')
  await dialog(page).getByLabel('启用', { exact: true }).uncheck()
  await save(page, `/api/business/partners/${partner.id}/`, 'PATCH', 200)
  expect(await admin.get(`business/partners/${partner.id}/`)).toMatchObject({ id: partner.id, name: `停用后单位${suffix}`, contact: '核对后联系人', is_active: false })

  await page.goto('/erp/purchases')
  await page.getByRole('button', { name: '新建采购', exact: true }).click()
  for (const [label, resource, name, id] of [
    ['供应商', 'partners', `停用后单位${suffix}`, partner.id],
    ['物料', 'items', `停用后物料${suffix}`, material.id],
  ] as const) {
    const control = dialog(page).locator('.remote-select').filter({ has: page.getByRole('combobox', { name: label, exact: true }) })
    await control.getByRole('textbox', { name: '搜索选项', exact: true }).fill(name)
    const pending = page.waitForResponse(response => {
      const url = new URL(response.url())
      return url.pathname === `/api/business/${resource}/` && url.searchParams.get('search') === name
    })
    await control.getByRole('button', { name: '搜索', exact: true }).click()
    const response = await pending
    expect(response.status()).toBe(200)
    expect(new URL(response.url()).searchParams.get('is_active')).toBe('true')
    expect((await response.json()).count).toBe(0)
    await expect(control.getByRole('combobox', { name: label, exact: true }).locator(`option[value="${id}"]`)).toHaveCount(0)
  }
  await dialog(page).getByRole('button', { name: '取消', exact: true }).click()
  await page.goto(`/erp/purchases?resource=purchases&focus=${purchase.id}`)
  await expect(dialog(page).getByRole('heading', { name: '查看明细', exact: true })).toBeVisible()
  await expect(dialog(page).getByRole('cell', { name: `停用后物料${suffix}`, exact: true })).toBeVisible()
  const preserved = await admin.get(`business/purchases/${purchase.id}/`)
  expect(preserved).toMatchObject({ id: purchase.id, code: oldOrder.code, supplier: partner.id, status: 'draft' })
  expect(preserved.lines[0]).toMatchObject({ id: oldOrder.lines[0].id, item: material.id, quantity: '1.000', unit_price: '10.00' })
  await page.screenshot({ path: info.outputPath('inactive-masterdata-original-purchase.png'), fullPage: true, animations: 'disabled' })
})
