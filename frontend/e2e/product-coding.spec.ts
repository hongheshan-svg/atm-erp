import { test, expect, login } from './fixtures'

test('BOM空编码导入预览不建物料，确认后自动建码并关联BOM', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = Date.now()
  async function post(path: string, data: object) {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBeLessThan(300)
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const customer = await post('partners/', { name: `自动导入客户${suffix}`, kind: 'customer' })
  const project = await post('projects/', { name: `自动导入项目${suffix}`, customer: customer.id, manager: me.id })
  await page.goto(`/erp/projects/${project.id}?tab=bom`)
  const region = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  const name = `空编码气缸${suffix}`
  const content = `物料编码,单元,需求数量,变更说明,需求日期,申请日期,申请人,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位\n,上料,2,新增,2026-10-01,2026-09-11,设计员,${name},ABC-10,,,21,SMC,standard,件\n`
  await region.locator('input[type=file]').setInputFiles({ name: 'auto.csv', mimeType: 'text/csv', buffer: Buffer.from(content) })
  await expect(region.locator('.import-preview')).toContainText('确认时自动生成')
  const before = await (await page.request.get('/api/business/items/?search=' + name, { headers })).json()
  expect(before.count).toBe(0)
  await region.locator('.import-preview').screenshot({ path: info.outputPath('auto-code-preview.png'), animations: 'disabled' })
  await region.getByRole('button', { name: '确认导入', exact: true }).click()
  const pending = page.waitForResponse(r => r.url().endsWith('/bom-import-confirm/'))
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(200)
  await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  const items = await (await page.request.get('/api/business/items/?search=' + name, { headers })).json()
  expect(items.count).toBe(1)
  expect(items.results[0].code).toMatch(/^2199\d{6}$/)
  const demand = await (await page.request.get(`/api/business/projects/${project.id}/demand/`, { headers })).json()
  expect(demand.lines[0].item).toBe(items.results[0].id)
  expect(demand.lines[0].quantity).toBe('2.000')
})

test('物料表单按有图类别自动编码并分离图号版本和品牌', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/masterdata?section=items')
  await page.getByRole('button', { name: '新增物料', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const drawing = `A26-E-05-P-${String(Date.now()).slice(-6)}`
  await dialog.getByLabel('物料名称', { exact: true }).fill(`台板${Date.now()}`)
  await dialog.getByLabel('规格', { exact: true }).fill('6061 300×200×20')
  await dialog.getByLabel('图号', { exact: true }).fill(drawing)
  await dialog.getByLabel('图档版本', { exact: true }).fill('A')
  await dialog.getByLabel('产品编码类别', { exact: true }).selectOption('11')
  await dialog.getByLabel('物料类别', { exact: true }).selectOption('custom')
  await page.screenshot({ path: info.outputPath('product-coding-form.png'), fullPage: true })
  const pending = page.waitForResponse(r => r.url().endsWith('/api/business/items/') && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(201)
  const id = (await response.json()).id
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const detail = await page.request.get(`/api/business/items/${id}/`, { headers: { Authorization: `Bearer ${token}` } })
  const item = await detail.json()
  expect(item.code).toMatch(/^11\d{8}$/)
  expect(item.brand).toBe('')
  expect(item.drawing_revision).toBe('A')
  expect(item.drawing_number).toBe(drawing)
  await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  const headers = { Authorization: `Bearer ${token}` }
  async function post(path: string, data: object) {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBeLessThan(300)
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const partner = await post('partners/', { name: `图档验证${Date.now()}`, kind: 'both' })
  const sale = await post('sales/', { name: `图档验证${Date.now()}`, customer: partner.id, manager: me.id })
  await post(`sales/${sale.id}/quote/`, { amount: '1000', reason: '图档验收' })
  const signed = await post(`sales/${sale.id}/sign/`, { date: '2026-09-11', manager: me.id, milestones: [{ title: '合同款', amount: '1000', due_date: '2026-10-01' }] })
  const purchase = await post('purchases/', { project: signed.project, supplier: partner.id, due_date: '2026-10-01', lines: [{ item: id, quantity: '1', unit_price: '100' }] })
  await page.goto(`/erp/purchases/${purchase.id}/contract`)
  const contract = page.getByRole('article', { name: '采购合同预览' })
  await expect(contract).toContainText(drawing)
  await expect(contract).toContainText(item.code)
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
  if (info.project.name === 'desktop') {
    const pdf = await page.pdf({ path: info.outputPath('coded-purchase-contract.pdf'), preferCSSPageSize: true, printBackground: true })
    expect(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)?.length).toBe(1)
  }
  await page.screenshot({ path: info.outputPath('coded-purchase-contract.png'), fullPage: true, animations: 'disabled' })
})
