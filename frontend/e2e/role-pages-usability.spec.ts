import { cancelEditing } from './fixtures'
import { test, expect, type Page } from './fixtures'

// Isolated read-only UI fixtures: every API call is intercepted. These cases verify entry points,
// context and layout; existing server permission/transaction tests remain the business evidence.
const project = { id: 7, code: 'PRJ-7', name: '装配检测线', customer_name: '测试客户', manager_name: '项目经理', status: 'active', equipment_quantity: 2, due_date: '2099-12-20', warranty_months: 12, can_manage: false, can_edit_bom: true }
const task = { id: 8, project: 7, project_name: project.name, title: '机械设计', due_date: '2099-10-30', status: 'open', kind: 'design', assignee: 9, assignee_name: '测试员工', can_manage: false }
const stock = { id: 2, item: 3, item_code: 'MAT-3', item_name: '伺服电机', specification: '750W', unit: '台', location: '主仓', quantity: '10.000', updated_at: '2026-10-21T00:00:00Z' }
async function fixture(page: Page, roles: string[]) {
  const calls: URL[] = []
  const writes: string[] = []
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-ui-fixture'))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url())
    calls.push(url)
    if (route.request().method() !== 'GET') writes.push(url.pathname)
    const list = (results: unknown[]) => ({ count: results.length, results, next: null, previous: null })
    let body: unknown = list([])
    if (url.pathname === '/api/auth/me/') body = { id: 9, username: 'ui-only', display_name: '测试员工', roles, setup_required: false }
    else if (url.pathname === '/api/business/workbench/') body = { tasks: { ...list([task]), page: 1, overdue_count: 0, today_count: 0 } }
    else if (url.pathname === '/api/business/projects/7/') body = { ...project, can_manage: roles.includes('admin') }
    else if (url.pathname === '/api/business/projects/') body = list([project])
    else if (url.pathname === '/api/business/projects/7/demand/') body = { revision: 'fixture', lines: [] }
    else if (url.pathname === '/api/business/tasks/8/') body = task
    else if (url.pathname === '/api/business/tasks/') body = list(url.searchParams.has('kind') ? [] : [task])
    else if (url.pathname === '/api/business/stocks/') body = list([stock])
    else if (url.pathname === '/api/business/stocks/locations/') body = ['主仓']
    else if (url.pathname === '/api/business/moves/') body = list([{ id: 6, stock: 2, project: 7, item_name: stock.item_name, location: '主仓', quantity: '-2.000', kind: 'issue', reason: '装配领料', created_at: '2026-10-21T00:00:00Z' }])
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  return { calls, writes }
}
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(await page.evaluate(() => window.innerWidth + 1))
}

test('工程师直接看见未到期任务，项目摘要保持范围，岗位指引可跳过再打开', async ({ page }, info) => {
  const { calls, writes } = await fixture(page, ['mechanical_engineer'])
  await page.goto('/erp/workbench')
  await expect(page.getByRole('heading', { name: '我正在做的工作' })).toBeVisible()
  await expect(page.locator('.work-ongoing')).toContainText('2099-10-30')
  await expect(page.locator('.work-ongoing')).toContainText(project.name)
  await expect(page.getByRole('link', { name: '继续处理机械设计' })).toBeInViewport()
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('engineer-workbench.png'), fullPage: true, animations: 'disabled' })
  await page.getByRole('link', { name: '继续处理机械设计' }).click()
  await expect(page).toHaveURL(/projects\/7\?tab=tasks&resource=tasks&focus=8/)
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  const summary = page.getByRole('region', { name: '项目待办摘要' })
  if (info.project.name === 'mobile') {
    const expand = summary.getByRole('button', { name: '展开项目待办', exact: true })
    await expect(expand).toHaveAttribute('aria-expanded', 'false')
    await expect(summary.getByRole('link', { name: /未完成任务/ })).toHaveCount(0)
    await expect(summary).toContainText('点击“展开项目待办”')
    await expand.click()
    await expect(summary.getByRole('button', { name: '收起项目待办', exact: true })).toHaveAttribute('aria-expanded', 'true')
  }
  await expect(summary).toContainText('未完成任务')
  await expect(summary).not.toContainText('采购')
  await summary.getByRole('link', { name: /未完成任务/ }).click()
  await expect(page).toHaveURL(/attention=open-tasks/)
  await expect(page.locator('.attention-filter')).toContainText('当前项目 · 未完成任务')
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('engineer-project.png'), fullPage: true, animations: 'disabled' })
  expect(calls.some(url => /purchases|entries|cost\//.test(url.pathname))).toBe(false)
  await page.goto('/erp/workbench')
  await page.getByRole('button', { name: '暂时跳过' }).click()
  await expect(page.getByRole('region', { name: '岗位首任务指引' }).getByRole('link')).toHaveCount(0)
  await page.getByRole('button', { name: '再次查看岗位指引' }).click()
  await expect(page.getByRole('link', { name: '维护 BOM' })).toBeVisible()
  expect(writes).toEqual([])
})

test('库存日常入口直达原收货、领料和退料流程，保留项目上下文', async ({ page }, info) => {
  const { calls, writes } = await fixture(page, ['warehouse'])
  await page.goto('/erp/inventory?section=receipts&project=7')
  await expect(page.getByRole('region', { name: '待收货采购', exact: true })).toBeVisible()
  await page.getByRole('navigation', { name: '收货进度' }).getByRole('link', { name: '部分收货采购' }).click()
  await expect(page.getByRole('region', { name: '部分收货采购', exact: true })).toBeVisible()
  expect(calls.some(url => url.pathname === '/api/business/purchases/' && url.searchParams.get('project') === '7' && url.searchParams.get('status') === 'partial')).toBe(true)
  await page.getByRole('navigation', { name: '日常库存操作' }).getByRole('link', { name: '项目领料' }).click()
  await expect(page.getByRole('button', { name: '领料', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '领料', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '领料', exact: true })).toBeVisible()
  await cancelEditing(page.getByRole('dialog', { name: '领料', exact: true }))
  await page.getByRole('navigation', { name: '日常库存操作' }).getByRole('link', { name: '项目退料' }).click()
  await expect(page.getByRole('region', { name: '原领料流水' })).toBeVisible()
  await expect(page.getByRole('button', { name: '退料', exact: true })).toBeVisible()
  expect(calls.some(url => url.pathname === '/api/business/moves/' && url.searchParams.get('project') === '7' && url.searchParams.get('kind') === 'issue')).toBe(true)
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('warehouse-returns.png'), fullPage: true, animations: 'disabled' })
  expect(writes).toEqual([])
})
