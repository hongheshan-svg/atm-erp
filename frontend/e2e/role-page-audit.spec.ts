import { cancelEditing } from './fixtures'
import { test, expect, login, accountTokens, type Page } from './fixtures'

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
  { key: 'purchase_manager', roles: ['purchase_manager'], pages: ['workbench', 'projects', 'bom', 'purchases', 'inventory', 'masterdata', 'settings'] },
  { key: 'mechanical_engineer', roles: ['mechanical_engineer'], pages: ['workbench', 'projects', 'bom', 'masterdata', 'settings'] },
  { key: 'electrical_engineer', roles: ['electrical_engineer'], pages: ['workbench', 'projects', 'bom', 'masterdata', 'settings'] },
  { key: 'production_manager', roles: ['production_manager'], pages: ['workbench', 'projects', 'bom', 'masterdata', 'settings'] },
]
const accounts: Record<string, { id: number; username: string }> = {}
const everyone = (...except: string[]) => identities.map(identity => identity.key).filter(key => !except.includes(key))
// 各页按岗位应看到的页签。roles 省略表示所有能进入该页的岗位都有；新增不分岗位的页签不必改这里，
// 逐页巡检仍会点开页面上实际出现的每个页签。
const pageTabs: Record<string, { label: string; roles?: string[] }[]> = {
  settings: [
    ...['用户管理', '公司资料', '编号规则', '操作审计', '管理员初始化', '历史数据核查'].map(label => ({ label, roles: ['admin'] })),
    { label: '我的账户' },
  ],
  masterdata: [
    { label: '物料', roles: everyone('sales_manager') },
    { label: '客户与供应商', roles: everyone('sales_manager') },
    { label: '客户资料', roles: ['sales_manager'] },
  ],
  inventory: [{ label: '现有库存' }, { label: '库存流水' }, { label: '领料单' }, { label: '采购收货', roles: ['admin', 'warehouse'] }],
  projects: [{ label: '项目列表' }, { label: '任务' }, { label: '工时记录' }],
  finance: [
    { label: '应收应付与费用' }, { label: '业务对账' }, { label: '供应商月度对账' }, { label: '收付款流水' },
    { label: '银行到账与认领', roles: ['admin', 'finance'] },
  ],
}
// 项目详情各页签下的子页签；BOM 只有一张表、成本与预算合为一个面板，均不再分子页签。
const projectChildTabs: Record<string, string[]> = {
  tasks: ['项目任务', '工时记录'],
  deliveries: ['交付批次', '售后任务'],
  finance: ['项目款项', '项目对账', '项目收付流水'],
  bom: [],
  cost: [],
}
const password = 'Eleven-role-audit-only-2026'
let projectId: number, otherProjectId: number

test.beforeAll(async ({ request }) => {
  const headers = { Authorization: `Bearer ${(await accountTokens(request, 'admin', process.env.E2E_ADMIN_PASSWORD!)).access}` }
  const suffix = Date.now()
  // 每个岗位使用独立账号；管理员也不继承前序用例累计的每分钟请求额度。
  // 保留正式限流和所有错误断言，避免快速巡检因共享测试身份产生顺序依赖。
  for (const identity of identities) {
    const response = await request.post('/api/auth/users/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: {
      username: `audit_${identity.key}_${suffix}`, display_name: `岗位验收${identity.key}`,
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
  const customer = await create('partners', { name: `岗位验收客户${suffix}`, kind: 'customer' })
  projectId = await create('projects', { name: `岗位页面巡检${suffix}`, customer, manager: accounts.manager!.id, members: ['member', 'general_manager', 'mechanical_engineer', 'electrical_engineer', 'production_manager'].map(key => accounts[key]!.id) })
  otherProjectId = await create('projects', { name: `成员不可见项目${suffix}`, customer, manager: accounts.admin!.id })
})

async function inspect(page: Page, visited: Record<string, unknown>[]) {
  await expect(page.locator('.el-loading-mask:visible, .el-button.is-loading:visible')).toHaveCount(0)
  if (new URL(page.url()).pathname.endsWith('/reports')) {
    await expect(page.getByRole('region', { name: '项目经营明细', exact: true })).toBeVisible()
    // 七项口径未减：四项作主指标卡，两项逾期收进对应主卡的说明，已承诺采购降到「经营关注」汇总行
    const metric = (label: string) => page.locator('.report-metric').filter({ has: page.getByText(label, { exact: true }) })
    for (const label of ['已签约合同额', '实际成本']) await expect(metric(label)).toHaveCount(1)
    for (const label of ['待收款', '待付款']) await expect(metric(label)).toContainText('其中逾期')
    const watch = page.getByRole('region', { name: '经营关注', exact: true })
    for (const label of ['已承诺采购', '待退客户款', '待收退款']) await expect(watch).toContainText(label)
  }
  await expect(page.locator('.el-alert--error:visible')).toHaveCount(0)
  const buttons = await page.getByRole('button').allTextContents()
  visited.push({ url: page.url(), buttons: buttons.map(s => s.trim()).filter(Boolean) })
  // Main document must remain usable; wide tables scroll inside their own panel.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true)
  for (const select of await page.locator('select[aria-label="每页显示条目"]:visible').all()) {
    // 项目内任务表每页至少 50 条，只提供 50/100 两档；其余列表从 10 切到 20 再切回。
    const sizes = await select.locator('option').evaluateAll(options => options.map(option => (option as HTMLOptionElement).value))
    const [other, restore] = sizes.includes('10') ? ['20', '10'] : [sizes[1]!, sizes[0]!]
    await select.selectOption(other)
    await expect(select).toHaveValue(other)
    await select.selectOption(restore)
    await expect(select).toHaveValue(restore)
  }
  for (const search of await page.getByRole('searchbox').all()) {
    await search.fill('不存在的验收记录-qa-none')
    await search.press('Enter')
    await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
    await search.fill('')
    await search.press('Enter')
  }
  // Covers every refresh control: the list icon button, the project page, and BOM's 刷新需求.
  for (const refresh of await page.getByRole('button', { name: /^刷新(列表|需求)?$/ }).all()) {
    await refresh.click()
    await expect(page.locator('.el-loading-mask:visible, .el-button.is-loading:visible')).toHaveCount(0)
  }
  const creators = page.getByRole('button', { name: /^(新增用户|新增物料|新增往来单位|新建项目|新建销售|新建采购|新建任务)$/ })
  for (const button of await creators.all()) {
    await button.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('button[type="submit"]')).toBeVisible()
    await dialog.locator('button[type="submit"]').click()
    await expect(dialog).toBeVisible()
    expect(await dialog.locator('input:invalid, select:invalid, textarea:invalid').count()).toBeGreaterThan(0)
    await cancelEditing(dialog)
    await expect(dialog).toBeHidden()
  }
  await expect(page.locator('.el-loading-mask:visible, .el-button.is-loading:visible')).toHaveCount(0)
  await expect(page.locator('.el-alert--error:visible')).toHaveCount(0)
}

for (const identity of identities) {
  test(`十一岗位逐页巡检：${identity.key}`, async ({ page }, info) => {
    test.setTimeout(240000)
    const visited: Record<string, unknown>[] = []
    await login(page, accounts[identity.key]!.username, password)
    const nav = page.getByRole('navigation', { name: '主导航', includeHidden: true })
    const hrefs = await nav.getByRole('link', { includeHidden: true }).evaluateAll(nodes => nodes.map(n => n.getAttribute('href')!.split('?')[0]!.replace('/erp/', '')))
    expect(hrefs).toEqual(identity.pages)
    for (const route of identity.pages) {
      await page.goto(`/erp/${route}`)
      await expect(page).toHaveURL(new RegExp(`/erp/${route}(?:\\?|$)`))
      await expect(page.locator('h1')).toBeVisible()
      // Assert expected tabs before enumerating: lazy rendering must not silently skip pages.
      for (const tab of pageTabs[route] ?? []) {
        const shown = !tab.roles || tab.roles.includes(identity.key)
        await expect(page.getByRole('tab', { name: tab.label, exact: true }), `${route} 页签「${tab.label}」`).toHaveCount(shown ? 1 : 0)
      }
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
      const tabs = ['tasks', 'bom', 'deliveries', 'documents', ...(['admin', 'general_manager', 'manager', 'purchaser', 'purchase_manager', 'warehouse', 'finance'].includes(identity.key) ? ['purchases'] : []), ...(['admin', 'manager', 'general_manager', 'finance'].includes(identity.key) ? ['finance', 'cost'] : [])]
      for (const tab of tabs) {
        await page.goto(`/erp/projects/${projectId}?tab=${tab}`)
        await expect(page.locator('h1')).toContainText('岗位页面巡检')
        // BOM 页签只有一张表（行内可改单行），不再分子页签；成本与预算合为一个面板，
        // 实际成本与毛利在指标卡里，成本来源从「追溯成本明细」打开。
        const childTabs = projectChildTabs[tab]
        if (childTabs) {
          const tabs = page.locator('.module-tabs').getByRole('tab')
          if (childTabs.length) for (const label of childTabs) await expect(tabs.filter({ hasText: label }), `${tab} 子页签「${label}」`).toHaveCount(1)
          else await expect(tabs).toHaveCount(0)
        }
        if (tab === 'cost') {
          const costPanel = page.getByRole('region', { name: '项目预算与成本管控', exact: true })
          for (const label of ['预算合计', '实际成本', '毛利（按实际）']) await expect(costPanel.getByRole('term').filter({ hasText: label })).toHaveCount(1)
          await expect(costPanel.getByRole('button', { name: '追溯成本明细', exact: true })).toBeVisible()
        }
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
    if (['member', 'mechanical_engineer', 'electrical_engineer', 'production_manager'].includes(identity.key)) {
      const hidden = await page.request.get(`/api/business/projects/${otherProjectId}/`, { headers })
      expect(hidden.status()).toBe(404)
    }
    await info.attach('page-operation-inventory', { body: JSON.stringify(visited, null, 2), contentType: 'application/json' })
  })
}
