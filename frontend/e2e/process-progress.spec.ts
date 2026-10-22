import { test, expect, login, openRowAction } from './fixtures'

test('项目相关人员和销售可查看流程节点与跟进人员，原单权限继续隔离', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': '' }
  const suffix = `${Date.now()}-${info.project.name}`
  const password = 'Progress-Isolated-2026'
  const today = new Date().toISOString().slice(0, 10)
  const due = new Date(Date.now() + 86400000).toISOString().slice(0, 10)
  const post = async (path: string, data: object, auth = headers) => {
    const response = await page.request.post(`/api/${path}`, { headers: { ...auth, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const staff: Record<string, { id: number; username: string }> = {}
  for (const [role, name] of [['mechanical_engineer', '设计张工'], ['purchase_manager', '采购李经理'], ['sales_manager', '销售王经理']]) {
    staff[role!] = await post('auth/users/', { username: `flow-${role}-${suffix}`, display_name: name, role, password })
  }
  const meResponse = await page.request.get('/api/auth/me/', { headers })
  expect(meResponse.ok()).toBeTruthy()
  const me = await meResponse.json()
  const customer = await post('business/partners/', { name: `进度客户${suffix}`, kind: 'customer' })
  const supplier = await post('business/partners/', { name: `进度供应商${suffix}`, kind: 'supplier' })
  const sale = await post('business/sales/', { name: `流程可见${suffix}`, customer: customer.id, manager: staff.sales_manager!.id })
  await post(`business/sales/${sale.id}/quote/`, { amount: '98765', reason: '隔离页面验收夹具' })
  const signed = await post(`business/sales/${sale.id}/sign/`, {
    date: today, manager: me.id, members: [staff.mechanical_engineer!.id],
    milestones: [{ title: '合同款', amount: '98765', due_date: due }],
  })
  const project = signed.project
  await post('business/tasks/', { project, kind: 'design', title: '图纸设计', assignee: staff.mechanical_engineer!.id, due_date: due })
  const item = await post('business/items/', { code: `FLOW-${suffix}`, name: `流程测试物料${suffix}`, specification: '测试规格', unit: '件' })
  const purchase = await post('business/purchases/', { project, supplier: supplier.id, due_date: due, lines: [{ item: item.id, quantity: '1', unit_price: '123.45' }] })
  await post(`business/purchases/${purchase.id}/submit/`, {})
  const purchaseResponse = await page.request.get(`/api/business/purchases/${purchase.id}/`, { headers })
  expect(purchaseResponse.ok()).toBeTruthy()
  const purchaseDetail = await purchaseResponse.json()

  await page.evaluate(() => localStorage.clear())
  await login(page, staff.mechanical_engineer!.username, password)
  await page.goto(`/erp/projects/${project}?tab=progress`)
  const progress = page.getByRole('region', { name: '流程进度', exact: true })
  await expect(progress).toContainText('图纸设计')
  await expect(progress).toContainText('设计张工')
  await progress.getByRole('button', { name: /采购到货/ }).click()
  await expect(progress).toContainText(purchaseDetail.code)
  await expect(progress).toContainText('采购李经理')
  await expect(progress.getByRole('link', { name: '查看原单' })).toHaveCount(0)
  await expect(progress).not.toContainText('123.45')
  await expect(progress).not.toContainText('98765')
  await progress.locator('summary').filter({ hasText: '查看流程节点' }).click()
  await expect(progress.locator('.process-current')).toContainText('待批准')
  await page.screenshot({ path: info.outputPath('participant-progress.png'), fullPage: true, animations: 'disabled' })
  const participantToken = await page.evaluate(() => localStorage.getItem('access_token'))
  const denied = await page.request.get(`/api/business/purchases/${purchase.id}/`, { headers: { Authorization: `Bearer ${participantToken}` } })
  expect(denied.status()).toBe(403)

  const approver = await post('auth/login/', { username: staff.purchase_manager!.username, password }, { Authorization: '', 'Idempotency-Key': '' })
  await post(`business/purchases/${purchase.id}/approve/`, {}, { Authorization: `Bearer ${approver.access}`, 'Idempotency-Key': '' })
  await progress.getByRole('button', { name: '刷新进度', exact: true }).click()
  await expect(progress.locator('.progress-status')).toHaveText('待收货')
  await progress.getByRole('button', { name: /收付款进度/ }).click()
  await expect(progress).toContainText('待起算付款')
  await expect(progress).not.toContainText('123.45')

  await page.evaluate(() => localStorage.clear())
  await login(page, staff.sales_manager!.username, password)
  await page.goto('/erp/sales')
  await page.locator('input[type="search"]').fill(`流程可见${suffix}`)
  await page.locator('form.resource-search').evaluate((form: HTMLFormElement) => form.requestSubmit())
  const row = page.locator('.el-table__body tr:visible').filter({ hasText: `流程可见${suffix}` })
  await expect(row).toHaveCount(1)
  await openRowAction(page, row, '交付与回款')
  const salesProgress = page.getByRole('region', { name: '流程进度', exact: true })
  await expect(salesProgress).toContainText('设计张工')
  await salesProgress.getByRole('button', { name: /采购到货/ }).click()
  await expect(salesProgress).toContainText('待收货')
  await expect(salesProgress.getByRole('link', { name: '查看原单' })).toHaveCount(0)
  const salesCard = salesProgress.locator('.progress-record').first()
  await salesCard.scrollIntoViewIfNeeded()
  const cardBounds = await salesCard.boundingBox()
  expect(cardBounds!.width).toBeGreaterThan(280)
  expect(cardBounds!.x).toBeGreaterThanOrEqual(0)
  expect(cardBounds!.x + cardBounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.screenshot({ path: info.outputPath('sales-progress.png'), fullPage: true, animations: 'disabled' })
})
