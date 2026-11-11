import { businessDate } from './fixtures'
import { test, expect, login } from './fixtures'

test('自编BOM编号保留前导零和厂家型号，确认后采购合同沿用原文', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const post = async (path: string, data: object) => {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const get = async (path: string) => {
    const response = await page.request.get('/api/' + path, { headers })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const suffix = Date.now() + '-' + info.project.name
  const code = '000-' + suffix
  const name = '自编气缸' + suffix
  const specification = 'ＭX-20  /  A(10)-' + suffix
  const me = await get('auth/me/')
  const customer = await post('partners/', { name: '编号客户' + suffix, kind: 'customer', code: 'C-' + suffix })
  const project = await post('projects/', { name: '编号验证' + suffix, customer: customer.id, manager: me.id, code: 'P-' + suffix })
  await page.goto('/erp/projects/' + project.id + '?tab=bom')
  const region = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await region.getByRole('button', { name: '导入 BOM', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导入BOM', exact: true })
  const content = '物料编码,单元,需求数量,变更说明,需求日期,申请日期,申请人,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位\n'
    + [code, '上料', '2', '厂家确认型号', '', '', '', name, specification, '', '', '', 'SMC', '标准件', 'PCS'].join(',') + '\n'
  await dialog.locator('input[type=file]').setInputFiles({ name: '自编BOM.csv', mimeType: 'text/csv', buffer: Buffer.from(content) })
  await expect(region.locator('.import-preview')).toContainText('按填写编码新建物料')
  await expect(region.locator('.import-preview')).toContainText(code)
  expect((await get('business/items/?search=' + encodeURIComponent(code))).count).toBe(0)
  await page.screenshot({ path: info.outputPath('manual-bom-preview.png'), animations: 'disabled' })
  await region.getByRole('button', { name: '确认导入', exact: true }).click()
  const pending = page.waitForResponse(r => r.url().endsWith('/bom-import-confirm/'))
  await page.getByRole('dialog').locator('button[type="submit"]').click()
  expect((await pending).status()).toBe(200)
  await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  const item = (await get('business/items/?search=' + encodeURIComponent(code))).results[0]
  expect(item.code).toBe(code)
  expect(item.specification).toBe(specification)
  const supplier = await post('partners/', { name: '编号供应商' + suffix, kind: 'supplier' })
  const po = await post('purchases/', {
    code: 'PO-' + suffix, project: project.id, supplier: supplier.id, due_date: businessDate(),
    lines: [{ item: item.id, quantity: '2', unit_price: '10' }],
  })
  const contract = await get('business/purchases/' + po.id + '/contract-preview/')
  expect(JSON.stringify(contract)).toContain(specification)
  expect(JSON.stringify(contract)).toContain(code)
})

test('往来单位页面可直接填写编号，留空仍可自动编号', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/masterdata?section=partners')
  const code = '000-UI-' + Date.now()
  await page.getByRole('button', { name: '新增往来单位', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('往来单位编码', { exact: true }).fill(code)
  await dialog.getByLabel('单位名称', { exact: true }).fill('自编编号界面验证' + code)
  await dialog.getByLabel('类型', { exact: true }).selectOption('customer')
  await expect(dialog).toContainText('可自行编号')
  await page.screenshot({ path: info.outputPath('manual-code-form.png'), animations: 'disabled' })
  const pending = page.waitForResponse(r => r.url().endsWith('/api/business/partners/') && r.request().method() === 'POST')
  await dialog.locator('button[type="submit"]').click()
  const response = await pending
  expect(response.status()).toBe(201)
  const saved = await response.json()
  await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const detail = await page.request.get('/api/business/partners/' + saved.id + '/', { headers: { Authorization: 'Bearer ' + token } })
  expect((await detail.json()).code).toBe(code)
})
