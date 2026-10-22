import { test, expect, login } from './fixtures'

test('管理员批量删除后可核对记录，普通岗位没有删除入口', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = `${Date.now()}-${info.project.name}`
  const name = `删除验收${suffix}`
  const ids: number[] = []
  for (const index of [1, 2]) {
    const response = await page.request.post('/api/business/partners/', {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { name: `${name}-${index}`, kind: 'customer' },
    })
    expect(response.status(), await response.text()).toBe(201)
    ids.push((await response.json()).id)
  }
  await page.goto('/erp/masterdata?section=partners')
  await page.locator('input[type="search"]').fill(name)
  await page.locator('form.resource-search').evaluate((element: HTMLFormElement) => element.requestSubmit())
  const rows = page.locator('.el-table__body tr:visible').filter({ hasText: name })
  await expect(rows).toHaveCount(2)
  for (const row of await rows.all()) await row.locator('.el-table-column--selection .el-checkbox').click()
  await page.getByRole('button', { name: '批量删除（2）', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText(`${name}-1`)
  await expect(dialog.getByRole('button', { name: '确认删除 2 条', exact: true })).toBeDisabled()
  await dialog.getByLabel('删除原因', { exact: true }).fill('隔离环境验收：清理误建资料')
  await dialog.getByRole('checkbox').check()
  await page.screenshot({ path: info.outputPath('delete-confirm.png'), animations: 'disabled' })
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/record-deletions/'))
  await dialog.getByRole('button', { name: '确认删除 2 条', exact: true }).click()
  expect((await pending).status()).toBe(200)
  await expect(dialog).toBeHidden()
  await expect(rows).toHaveCount(0)
  await page.getByRole('button', { name: '已删除记录', exact: true }).click()
  await expect(dialog).toContainText(`${name}-1`)
  await expect(dialog).toContainText('隔离环境验收：清理误建资料')
  await dialog.getByRole('button', { name: '查看删除时内容', exact: true }).first().click()
  await expect(dialog.locator('dl')).toContainText(name)
  await page.screenshot({ path: info.outputPath('deleted-history.png'), animations: 'disabled' })
  const history = await page.request.get('/api/business/record-deletions/?resource=partners', { headers })
  expect(history.status()).toBe(200)
  expect((await history.json()).results.filter((record: { detail: { record: { id: number } } }) => ids.includes(record.detail.record.id))).toHaveLength(2)

  const username = `deletion_finance_${suffix}`, password = 'Deletion-Test-Only-2026'
  const created = await page.request.post('/api/auth/users/', {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { username, password, display_name: '删除权限验收', role: 'finance' },
  })
  expect(created.status(), await created.text()).toBe(201)
  await page.evaluate(() => localStorage.clear())
  await login(page, username, password)
  await page.goto('/erp/finance?section=entries')
  await expect(page.locator('h1')).toContainText('收付款')
  await expect(page.getByRole('button', { name: /批量删除|已删除记录/ })).toHaveCount(0)
  const financeToken = await page.evaluate(() => localStorage.getItem('access_token'))
  const denied = await page.request.post('/api/business/record-deletions/', {
    headers: { Authorization: `Bearer ${financeToken}`, 'Idempotency-Key': crypto.randomUUID() },
    data: { resource: 'partners', ids, reason: '越权应拒绝' },
  })
  expect(denied.status()).toBe(403)
})

test('BOM独立列表及销售附件支持删除和已删除记录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = `${Date.now()}-${info.project.name}`
  const get = async (path: string) => {
    const response = await page.request.get(`/api/${path}`, { headers })
    expect(response.status(), await response.text()).toBe(200)
    return response.json()
  }
  const post = async (path: string, data: object) => {
    const response = await page.request.post(`/api/business/${path}`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await get('auth/me/')
  const partner = await post('partners/', { name: `删除独立列表${suffix}`, kind: 'customer' })
  const project = await post('projects/', { name: `BOM删除${suffix}`, customer: partner.id, manager: me.id })
  const item = await post('items/', { code: `DEL-${suffix}`, name: `删除物料${suffix}`, specification: '测试', unit: '件' })
  const demand = await get(`business/projects/${project.id}/demand/`)
  await post(`projects/${project.id}/revise-bom/`, { expected_revision: demand.revision, lines: [
    { item: item.id, assembly_unit: 'A单元', quantity: '2', change_note: '首次录入' },
    { item: item.id, assembly_unit: 'B单元', quantity: '3', change_note: '首次录入' },
  ] })
  await page.goto(`/erp/projects/${project.id}?tab=bom`)
  const bom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await expect(bom).toBeVisible()
  const rows = bom.locator('.el-table__body tr:visible')
  await expect(rows).toHaveCount(2)
  for (const row of await rows.all()) await row.locator('.el-table-column--selection .el-checkbox').click()
  await bom.getByRole('button', { name: '批量删除（2）', exact: true }).click()
  let dialog = page.getByRole('dialog', { name: '确认删除 2 条BOM明细', exact: true })
  await dialog.getByLabel('删除原因').fill('误建两条用料')
  await dialog.getByRole('checkbox').check()
  await dialog.getByRole('button', { name: '确认删除 2 条', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(bom).toContainText('尚未维护 BOM')
  expect((await get(`business/projects/${project.id}/demand/`)).lines).toHaveLength(0)
  await bom.getByRole('button', { name: '已删除记录', exact: true }).click()
  dialog = page.getByRole('dialog', { name: 'BOM明细 · 已删除记录', exact: true })
  await expect(dialog.locator('article')).toHaveCount(2)
  await page.screenshot({ path: info.outputPath('bom-deleted-history.png'), animations: 'disabled' })
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()

  const sale = await post('sales/', { name: `附件删除${suffix}`, customer: partner.id, manager: me.id })
  const uploaded = await page.request.post('/api/business/documents/', {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, multipart: {
      sale: String(sale.id), category: 'other', file: { name: `误传${suffix}.txt`, mimeType: 'text/plain', buffer: Buffer.from('隔离测试资料') },
    },
  })
  expect(uploaded.status(), await uploaded.text()).toBe(201)
  await page.goto('/erp/sales')
  await page.locator('input[type="search"]').fill(`附件删除${suffix}`)
  await page.locator('form.resource-search').evaluate((element: HTMLFormElement) => element.requestSubmit())
  const saleRow = page.locator('.el-table__body tr:visible').filter({ hasText: `附件删除${suffix}` })
  await saleRow.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name: '附件', exact: true }).click()
  const attachments = page.getByRole('dialog').filter({ has: page.getByRole('button', { name: '上传附件', exact: true }) })
  await expect(attachments).toContainText(`误传${suffix}.txt`)
  await attachments.getByRole('button', { name: '删除', exact: true }).click()
  dialog = page.getByRole('dialog', { name: '确认删除 1 条附件', exact: true })
  await dialog.getByLabel('删除原因').fill('附件误传验收')
  await dialog.getByRole('checkbox').check()
  await dialog.getByRole('button', { name: '确认删除 1 条', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(attachments).not.toContainText(`误传${suffix}.txt`)
  await attachments.getByRole('button', { name: '已删除记录', exact: true }).click()
  dialog = page.getByRole('dialog', { name: '附件 · 已删除记录', exact: true })
  await expect(dialog.locator('article')).toHaveCount(1)
  await expect(dialog).toContainText('附件误传验收')
  await page.screenshot({ path: info.outputPath('attachment-deleted-history.png'), animations: 'disabled' })
})
