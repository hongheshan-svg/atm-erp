import { test, expect, login, type Page } from './fixtures'

// Fixtures use the public API; successful business mutations are covered by full-chain.spec.ts.
// Expected navigation is deliberately independent of the production navigation helper.
const identities = [
  { key: 'admin', roles: ['admin'], pages: ['workbench', 'reports', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'] },
  { key: 'general_manager', roles: ['manager'], pages: ['workbench', 'reports', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'] },
  { key: 'manager', roles: ['manager'], pages: ['workbench', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'] },
  { key: 'sales_manager', roles: ['sales_manager'], pages: ['workbench', 'sales', 'masterdata', 'settings'] },
  { key: 'purchaser', roles: ['purchaser'], pages: ['workbench', 'projects', 'bom', 'purchases', 'inventory', 'masterdata', 'settings'] },
  { key: 'warehouse', roles: ['warehouse'], pages: ['workbench', 'projects', 'bom', 'purchases', 'inventory', 'masterdata', 'settings'] },
  { key: 'finance', roles: ['finance'], pages: ['workbench', 'sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'settings'] },
  { key: 'member', roles: ['member'], pages: ['workbench', 'projects', 'bom', 'masterdata', 'settings'] },
]
const accounts: Record<string, { id: number; username: string }> = {}
const password = 'Eight-role-audit-only-2026'
let projectId: number, otherProjectId: number

test.beforeAll(async ({ request }) => {
  const auth = await request.post('/api/auth/login/', { data: { username: 'admin', password: process.env.E2E_ADMIN_PASSWORD } })
  expect(auth.status()).toBe(200)
  const headers = { Authorization: `Bearer ${(await auth.json()).access}` }
  const me = await request.get('/api/auth/me/', { headers })
  accounts.admin = await me.json()
  const suffix = Date.now()
  for (const identity of identities.slice(1)) {
    const response = await request.post('/api/auth/users/', { headers, data: {
      username: `audit_${identity.key}_${suffix}`, display_name: `八岗验收${identity.key}`,
      roles: identity.roles, password, management_reports: identity.key === 'general_manager',
    } })
    expect(response.status(), await response.text()).toBe(201)
    accounts[identity.key] = await response.json()
  }
  async function create(path: string, data: Record<string, unknown>) {
    const response = await request.post(`/api/business/${path}/`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBe(201)
    return (await response.json()).id as number
  }
  const customer = await create('partners', { name: `八岗验收客户${suffix}`, kind: 'customer' })
  projectId = await create('projects', { name: `八岗页面巡检${suffix}`, customer, manager: accounts.manager!.id, members: [accounts.member!.id, accounts.general_manager!.id] })
  otherProjectId = await create('projects', { name: `成员不可见项目${suffix}`, customer, manager: accounts.admin!.id })
})

async function inspect(page: Page, visited: Record<string, unknown>[]) {
  await expect(page.locator('.el-loading-mask:visible, .el-button.is-loading:visible')).toHaveCount(0)
  if (new URL(page.url()).pathname.endsWith('/reports')) {
    await expect(page.getByRole('region', { name: '项目经营明细', exact: true })).toBeVisible()
    await expect(page.locator('.report-metric')).toHaveCount(7)
  }
  await expect(page.locator('.el-alert--error:visible')).toHaveCount(0)
  const buttons = await page.getByRole('button').allTextContents()
  visited.push({ url: page.url(), buttons: buttons.map(s => s.trim()).filter(Boolean) })
  // Main document must remain usable; wide tables scroll inside their own panel.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true)
  for (const select of await page.locator('select[aria-label="每页显示条目"]:visible').all()) {
    await select.selectOption('20')
    await expect(select).toHaveValue('20')
    await select.selectOption('10')
  }
  for (const search of await page.getByRole('searchbox').all()) {
    await search.fill('不存在的验收记录-qa-none')
    await search.press('Enter')
    await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
    await search.fill('')
    await search.press('Enter')
  }
  for (const refresh of await page.getByRole('button', { name: '刷新', exact: true }).all()) {
    await refresh.click()
    await expect(page.locator('.el-loading-mask:visible, .el-button.is-loading:visible')).toHaveCount(0)
  }
  const creators = page.getByRole('button', { name: /^(新增用户|新增物料|新增往来单位|新建项目|新建销售|新建采购|新建任务)$/ })
  for (const button of await creators.all()) {
    await button.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeVisible()
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog).toBeVisible()
    expect(await dialog.locator('input:invalid, select:invalid, textarea:invalid').count()).toBeGreaterThan(0)
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
    await expect(dialog).toBeHidden()
  }
  await expect(page.locator('.el-loading-mask:visible, .el-button.is-loading:visible')).toHaveCount(0)
  await expect(page.locator('.el-alert--error:visible')).toHaveCount(0)
}

for (const identity of identities) {
  test(`八岗逐页巡检：${identity.key}`, async ({ page }, info) => {
    test.setTimeout(240000)
    const visited: Record<string, unknown>[] = []
    await login(page, accounts[identity.key]!.username, identity.key === 'admin' ? process.env.E2E_ADMIN_PASSWORD! : password)
    const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
    const hrefs = await nav.getByRole('link', { includeHidden: true }).evaluateAll(nodes => nodes.map(n => n.getAttribute('href')!.split('?')[0]!.replace('/erp/', '')))
    expect(hrefs).toEqual(identity.pages)
    for (const route of identity.pages) {
      await page.goto(`/erp/${route}`)
      await expect(page).toHaveURL(new RegExp(`/erp/${route}(?:\\?|$)`))
      await expect(page.locator('h1')).toBeVisible()
      const tabCount: Record<string, number> = {
        settings: identity.key === 'admin' ? 5 : 1,
        masterdata: identity.key === 'sales_manager' ? 1 : 2,
        inventory: 2,
        finance: ['admin', 'finance'].includes(identity.key) ? 5 : 4,
      }
      // Assert expected tabs before enumerating: lazy rendering must not silently skip pages.
      await expect(page.getByRole('tab')).toHaveCount(tabCount[route] ?? 0)
      await inspect(page, visited)
      const labels = await page.getByRole('tab').allTextContents()
      for (const label of labels) {
        const tab = page.getByRole('tab', { name: label.trim(), exact: true })
        await tab.focus()
        await tab.press('Enter')
        await expect(tab).toHaveAttribute('aria-selected', 'true')
        await inspect(page, visited)
      }
      await page.screenshot({ path: info.outputPath(`${identity.key}-${route}.png`), fullPage: true, animations: 'disabled' })
    }
    for (const denied of identities[0]!.pages.filter(p => !identity.pages.includes(p))) {
      await page.goto(`/erp/${denied}`)
      await expect(page).toHaveURL(/\/erp\/workbench$/)
    }
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    const headers = { Authorization: `Bearer ${token}` }
    const users = await page.request.get('/api/auth/users/', { headers })
    expect(users.status()).toBe(identity.key === 'admin' ? 200 : 403)
    const reports = await page.request.get('/api/business/reports/', { headers })
    expect(reports.status()).toBe(['admin', 'general_manager'].includes(identity.key) ? 200 : 403)
    if (identity.pages.includes('projects')) {
      const tabs = ['tasks', 'bom', 'deliveries', 'documents', ...(identity.key !== 'member' ? ['purchases'] : []), ...(['admin', 'manager', 'general_manager', 'finance'].includes(identity.key) ? ['finance', 'cost'] : [])]
      for (const tab of tabs) {
        await page.goto(`/erp/projects/${projectId}?tab=${tab}`)
        await expect(page.locator('h1')).toContainText('八岗页面巡检')
        const childTabs: Record<string, number> = { tasks: 2, bom: 2, deliveries: 2, finance: 3, cost: 2 }
        await expect(page.locator('.module-tabs').getByRole('tab')).toHaveCount(childTabs[tab] ?? 0)
        await inspect(page, visited)
        const labels = await page.locator('.module-tabs').getByRole('tab').allTextContents()
        for (const label of labels) {
          await page.locator('.module-tabs').getByRole('tab', { name: label.trim(), exact: true }).click()
          await inspect(page, visited)
        }
      }
      const cost = await page.request.get(`/api/business/projects/${projectId}/cost/`, { headers })
      expect(cost.status()).toBe(['admin', 'manager', 'general_manager', 'finance'].includes(identity.key) ? 200 : 403)
    }
    if (identity.key === 'member') {
      const hidden = await page.request.get(`/api/business/projects/${otherProjectId}/`, { headers })
      expect(hidden.status()).toBe(404)
    }
    await info.attach('page-operation-inventory', { body: JSON.stringify(visited, null, 2), contentType: 'application/json' })
  })
}
