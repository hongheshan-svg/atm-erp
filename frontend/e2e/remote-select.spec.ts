import { test, expect } from './fixtures'
import { clearRemote, remoteControl, searchRemote, selectRemoteOption } from './remote-select-helpers'

// 仅验证真实浏览器中的组合框与父子表单交互；全部 API 为隔离夹具，不替代服务端权限验证。
test('远程组合框键盘、分页与就近建档保留父表单', async ({ page }, info) => {
  const profile = { id: 1, username: 'selector_qa', display_name: '选择器验收', roles: ['sales_manager'] }
  const customers = Array.from({ length: 22 }, (_, index) => ({ id: index + 1, name: '同名客户', code: `C${String(index + 1).padStart(3, '0')}`, kind: 'customer', is_active: true }))
  let created: typeof customers[number] | undefined
  const writes: { path: string; body: Record<string, unknown> }[] = []
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-selector-test-token'))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url())
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      writes.push({ path: url.pathname, body })
      if (url.pathname === '/api/business/partners/') {
        created = { id: 101, name: String(body.name), code: 'C101', kind: body.kind, is_active: true }
        return route.fulfill({ status: 201, json: created })
      }
      return route.fulfill({ status: 200, json: { id: 999 } })
    }
    if (url.pathname === '/api/auth/me/') return route.fulfill({ json: profile })
    if (url.pathname === '/api/auth/directory/') return route.fulfill({ json: [profile] })
    if (url.pathname === '/api/business/partners/101/') return route.fulfill({ json: created })
    if (url.pathname === '/api/business/partners/') {
      const search = url.searchParams.get('search') || ''
      const matches = [...customers, ...(created ? [created] : [])].filter(row => `${row.name} ${row.code}`.includes(search))
      const pageNumber = Number(url.searchParams.get('page') || 1)
      return route.fulfill({ json: { count: matches.length, results: matches.slice((pageNumber - 1) * 20, pageNumber * 20), next: pageNumber * 20 < matches.length ? '?page=2' : null } })
    }
    return route.fulfill({ json: { count: 0, results: [], next: null } })
  })
  await page.goto('/erp/sales')
  await page.getByRole('button', { name: '新建销售', exact: true }).click()
  const parent = page.getByRole('dialog', { name: '新建销售', exact: true })
  await parent.getByLabel('销售名称', { exact: true }).fill('父表单待保存内容')
  const customer = parent.getByRole('combobox', { name: '客户', exact: true })
  await searchRemote(customer, '同名客户')
  await expect(remoteControl(customer).locator('select')).toHaveCount(0)
  await customer.press('ArrowDown')
  await customer.press('ArrowDown')
  await customer.press('Enter')
  await expect(customer).toHaveValue('同名客户 · C002')
  await selectRemoteOption(customer, { text: '同名客户', id: 22 })
  await expect(customer).toHaveValue('同名客户 · C022')

  // 重新键入只代表搜索，绝不能把之前的 C022 当作新输入提交。
  await customer.fill('未选中的另一客户')
  await parent.locator('button[type="submit"]').click()
  await expect(parent.getByRole('alert', { name: '填写问题汇总' })).toContainText('客户')
  expect(writes).toHaveLength(0)
  await expect(customer).toHaveValue('未选中的另一客户')

  const control = await searchRemote(customer, '就近新建客户')
  await expect(control.getByRole('status')).toHaveText('无匹配结果')
  await control.getByRole('button', { name: '新增客户', exact: true }).click()
  let child = page.getByRole('dialog', { name: '新增客户', exact: true })
  await expect(child).toBeVisible()
  await expect(child.getByLabel('单位名称', { exact: true })).toHaveValue('就近新建客户')
  await page.screenshot({ path: info.outputPath(`remote-create-${info.project.name}.png`), animations: 'disabled' })
  await child.getByLabel('单位名称', { exact: true }).press('Escape')
  await expect(child).toHaveCount(0)
  await expect(parent).toBeVisible()
  await expect(parent.getByLabel('销售名称', { exact: true })).toHaveValue('父表单待保存内容')

  await searchRemote(customer, '就近新建客户')
  await control.getByRole('button', { name: '新增客户', exact: true }).click()
  child = page.getByRole('dialog', { name: '新增客户', exact: true })
  await child.locator('button[type="submit"]').click()
  await expect(child).toHaveCount(0)
  await expect(customer).toHaveValue('就近新建客户 · C101')
  await expect(customer).toBeEnabled()
  await expect(parent.getByLabel('销售名称', { exact: true })).toHaveValue('父表单待保存内容')
  expect(writes).toEqual([{ path: '/api/business/partners/', body: expect.objectContaining({ name: '就近新建客户', kind: 'customer' }) }])
  await clearRemote(customer)
  await searchRemote(customer, '同名客户')
  await page.screenshot({ path: info.outputPath(`remote-select-${info.project.name}.png`), animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
})
