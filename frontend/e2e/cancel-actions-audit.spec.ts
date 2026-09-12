import { test, expect, login, type Page, type Locator } from './fixtures'

const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, value: string) => page.locator('.el-table__body tr:visible').filter({ hasText: value }).first()
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
async function action(page: Page, target: Locator, name: string) {
  await target.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(page)).toBeVisible()
}
async function projectAction(page: Page, name: string) {
  await page.getByRole('button', { name: '项目操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(page)).toBeVisible()
}
async function save(page: Page, suffix: string, reason: string) {
  await dialog(page).getByLabel('原因 / 说明', { exact: true }).fill(reason)
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(suffix))
  await dialog(page).getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(200)
  await expect(dialog(page)).toBeHidden()
}

test('销售经理从工作台定位订单并取消草稿，保留原销售记录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const admin = await api(page), suffix = `${Date.now()}-${info.project.name}`
  const password = 'Sales-cancel-audit-2026-only'
  const person = await admin.post('auth/users/', { username: `cancel_sales_${Date.now()}`, display_name: '销售取消验收', roles: ['sales_manager'], password })
  const customer = await admin.post('business/partners/', { name: `取消验收客户${suffix}`, kind: 'customer' })
  const created = await admin.post('business/sales/', { name: `取消验收销售${suffix}`, customer: customer.id, manager: person.id })
  const sale = await admin.get(`business/sales/${created.id}/`)
  await login(page, person.username, password)
  await page.evaluate(({ id }) => sessionStorage.setItem(`resource-search-${id}-sales-{}`, '旧搜索不应覆盖工作台单号'), { id: person.id })
  await page.getByRole('region', { name: '我的销售订单', exact: true }).locator('a.work-item').filter({ hasText: sale.code }).click()
  await expect(page).toHaveURL(new RegExp(`/erp/sales\\?search=${sale.code}`))
  await expect(page.getByRole('searchbox', { name: '搜索销售订单', exact: true })).toHaveValue(sale.code)
  await expect(row(page, sale.name)).toBeVisible()
  await action(page, row(page, sale.name), '取消销售')
  await save(page, `/sales/${sale.id}/cancel/`, '客户暂停需求，保留原销售草稿')
  const cancelled = await admin.get(`business/sales/${sale.id}/`)
  expect(cancelled).toMatchObject({ id: sale.id, name: sale.name, code: sale.code, status: 'cancelled', project: null })
  await expect(row(page, sale.name)).toContainText('已取消')
  await row(page, sale.name).getByRole('button', { name: '操作 ▾', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: '取消销售', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.screenshot({ path: info.outputPath('cancelled-sale.png'), fullPage: true, animations: 'disabled' })
})

test('项目编辑取消重开、BOM移除及已付款费用取消均保留业务依据', async ({ page }, info) => {
  test.setTimeout(150000)
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const admin = await api(page), suffix = `${Date.now()}-${info.project.name}`
  const me = await admin.get('auth/me/')
  const customer = await admin.post('business/partners/', { name: `项目取消客户${suffix}`, kind: 'customer' })
  const created = await admin.post('business/projects/', { name: `取消前项目${suffix}`, customer: customer.id, manager: me.id })
  const project = await admin.get(`business/projects/${created.id}/`)
  const task = await admin.post('business/tasks/', { project: project.id, title: `待办保留${suffix}`, kind: 'design', assignee: me.id })
  const material = await admin.post('business/items/', { name: `移除BOM物料${suffix}`, unit: '件' })
  const originalDemand = await admin.get(`business/projects/${project.id}/demand/`)
  await admin.post(`business/projects/${project.id}/revise-bom/`, { expected_revision: originalDemand.revision, lines: [{ item: material.id, quantity: '2', change_note: '初版，用于验证移除保留依据', assembly_unit: '上料单元' }] })
  const bom = (await admin.get(`business/bom/?project=${project.id}`)).results[0]

  await page.goto(`/erp/projects/${project.id}`)
  await projectAction(page, '编辑项目')
  await dialog(page).getByLabel('项目名称', { exact: true }).fill(`编辑后项目${suffix}`)
  await dialog(page).getByLabel('需求说明', { exact: true }).fill('设备名称按合同校对，单元方案变更')
  await save(page, `/projects/${project.id}/edit/`, '校对项目名称与设备范围')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(`编辑后项目${suffix}`)
  expect(await admin.get(`business/projects/${project.id}/`)).toMatchObject({ id: project.id, code: project.code, requirements: '设备名称按合同校对，单元方案变更' })

  await page.goto(`/erp/projects/${project.id}?tab=bom&section=lines`)
  await action(page, row(page, `移除BOM物料${suffix}`), '移除')
  const removeReason = `ECN移除未采购物料${suffix}`
  await save(page, `/bom/${bom.id}/remove/`, removeReason)
  await expect(page.getByRole('region', { name: 'BOM 明细', exact: true })).toContainText('暂无记录')
  expect((await admin.get(`business/bom/?project=${project.id}`)).count).toBe(0)
  expect((await admin.get(`business/projects/${project.id}/demand/`)).lines).toHaveLength(0)
  expect(await admin.get(`business/items/${material.id}/`)).toMatchObject({ id: material.id, name: `移除BOM物料${suffix}` })
  const audit = await admin.get('core/audit/?page_size=100')
  expect(audit.results.some((record: { operation: string; resource: string; detail: { reason?: string } }) => record.operation === 'bom.remove' && record.resource === `bomline:${bom.id}` && record.detail.reason === removeReason)).toBe(true)

  await projectAction(page, '取消项目')
  await save(page, `/projects/${project.id}/cancel/`, '现场计划暂停，待重新评估')
  expect(await admin.get(`business/projects/${project.id}/`)).toMatchObject({ id: project.id, code: project.code, status: 'cancelled' })
  expect(await admin.get(`business/tasks/${task.id}/`)).toMatchObject({ id: task.id, status: 'cancelled' })
  await projectAction(page, '重新打开')
  await save(page, `/projects/${project.id}/reopen/`, '客户确认恢复执行')
  expect(await admin.get(`business/projects/${project.id}/`)).toMatchObject({ id: project.id, code: project.code, status: 'active' })
  expect(await admin.get(`business/tasks/${task.id}/`)).toMatchObject({ id: task.id, status: 'cancelled' })

  const day = new Date().toLocaleDateString('sv-SE')
  const expense = await admin.post('business/entries/expense/', { project: project.id, title: `取消已付款费用${suffix}`, amount: '50', due_date: day })
  const payment = await admin.post(`business/entries/${expense.id}/pay/`, { amount: '50', date: day, reason: '已付现场差旅，后续取消应保留原流水', method: 'cash' })
  await page.goto(`/erp/projects/${project.id}?tab=finance&section=entries`)
  await action(page, row(page, `取消已付款费用${suffix}`), '取消费用')
  await save(page, `/entries/${expense.id}/cancel-expense/`, '行程取消，已支付金额转为待退款')
  expect(await admin.get(`business/entries/${expense.id}/`)).toMatchObject({ id: expense.id, cancelled: true, amount: '50.00', credit_amount: '50.00', paid_amount: '50.00', balance: '-50.00' })
  const payments = await admin.get(`business/payments/?entry=${expense.id}`)
  expect(payments.count).toBe(1)
  expect(payments.results[0]).toMatchObject({ id: payment.id, amount: '50.00', reversal_of: null, reversed_by: null })
  await expect(row(page, `取消已付款费用${suffix}`)).toContainText('待退款 50.00')
  await page.screenshot({ path: info.outputPath('cancelled-paid-expense.png'), fullPage: true, animations: 'disabled' })
})
