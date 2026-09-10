import { test, expect, login } from './fixtures'

test('签署版本归档后保持原资料，整套打印且经营关注只读展开', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }, prefix = `版本验收${Date.now()}`
  const day = new Date().toISOString().slice(0, 10)
  async function post(path: string, data: object) {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBeLessThan(300)
    return response.json()
  }
  const companyResponse = await page.request.get('/api/core/company/', { headers })
  const listing = await companyResponse.json(), company = (listing.results || listing)[0]
  const oldCompany = { name: company.name, address: company.address, phone: company.phone }
  const configured = await page.request.patch('/api/core/company/1/', { headers, data: { address: '隔离测试采购方地址', phone: '000-12345' } })
  expect(configured.ok()).toBeTruthy()
  try {
    const me = await (await page.request.get('/api/auth/me/', { headers })).json()
    const partner = await post('partners/', { name: prefix, kind: 'both', address: '归档前供应商地址', phone: '000-67890' })
    const material = await post('items/', { name: prefix + '物料', unit: '件' })
    const sale = await post('sales/', { name: prefix, customer: partner.id, manager: me.id })
    await post(`sales/${sale.id}/quote/`, { amount: '1000', reason: '隔离测试' })
    const signed = await post(`sales/${sale.id}/sign/`, { date: day, manager: me.id, milestones: [{ title: '合同款', amount: '1000', due_date: day }] })
    const purchase = await post('purchases/', { project: signed.project, supplier: partner.id, due_date: day, lines: [{ item: material.id, quantity: '1', unit_price: '100' }] })
    await post(`purchases/${purchase.id}/submit/`, {})
    await post(`purchases/${purchase.id}/approve/`, { reason: '隔离测试管理员自批例外' })
    const uploaded = await page.request.post('/api/business/documents/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, multipart: { purchase: String(purchase.id), category: 'contract', file: { name: '隔离测试签署样本.txt', mimeType: 'text/plain', buffer: Buffer.from('自动验收样本，不是企业真实签署合同') } } })
    expect(uploaded.status()).toBe(201)
    const document = await uploaded.json()
    await page.goto(`/erp/purchases/${purchase.id}/contract`)
    await page.getByRole('button', { name: '归档签署版本', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('已签署合同附件', { exact: true }).selectOption(String(document.id))
    await dialog.getByLabel('双方确认的收货地址', { exact: true }).fill('隔离验收收货地点')
    await dialog.getByLabel('归档或修订原因', { exact: true }).fill('自动测试样本核对')
    await dialog.getByLabel('已核对签署文件与本版正文、明细及收货地址一致', { exact: true }).check()
    const pending = page.waitForResponse(r => r.url().endsWith('/archive-contract/'))
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    expect((await pending).status()).toBe(201)
    await expect(page.getByText('当前为已归档第 1 版，资料保持不变', { exact: true })).toBeVisible()
    const changed = await page.request.patch(`/api/business/partners/${partner.id}/`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { address: '归档后新地址' } })
    expect(changed.ok()).toBeTruthy()
    await page.getByRole('button', { name: '刷新预览', exact: true }).click()
    await expect(page.getByRole('article')).toContainText('归档前供应商地址')
    await expect(page.getByRole('article')).not.toContainText('归档后新地址')
    await page.getByLabel('正文与完整附件一起打印', { exact: true }).check()
    await expect(page.getByRole('article')).toHaveCount(2)
    await page.emulateMedia({ media: 'print' })
    await expect(page.locator('.el-message:visible')).toHaveCount(0)
    const pdf = await page.pdf({ path: info.outputPath('contract-package.pdf'), preferCSSPageSize: true, printBackground: true })
    expect((pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length).toBe(2)
    await page.emulateMedia({ media: 'screen' })
    await page.screenshot({ path: info.outputPath('contract-archive.png'), animations: 'disabled', fullPage: true })
    await page.goto('/erp/reports')
    await page.getByRole('button', { name: '展开资金与采购库存关注', exact: true }).click()
    for (const view of ['aging', 'late_purchase', 'stale_stock', 'cash30']) {
      const response = page.waitForResponse(r => r.url().includes('/api/business/reports/?') && r.url().includes(`view=${view}`))
      await page.getByLabel('经营关注视图', { exact: true }).selectOption(view)
      expect((await response).status()).toBe(200)
    }
    await page.screenshot({ path: info.outputPath('report-attention.png'), animations: 'disabled', fullPage: true })
  } finally {
    const restored = await page.request.patch('/api/core/company/1/', { headers, data: oldCompany })
    expect(restored.ok()).toBeTruthy()
  }
})
