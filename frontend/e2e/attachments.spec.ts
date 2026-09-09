import { test, expect, login } from './fixtures'
import { readFile } from 'node:fs/promises'
test('合同附件从真实表单上传且只能鉴权下载', async ({ page }, info) => {
  const password = process.env.E2E_ADMIN_PASSWORD
  expect(password).toBeTruthy()
  await login(page, 'admin', password!)
  const suffix = String(Date.now())
  const customer = '附件客户' + suffix
  const project = '附件项目' + suffix
  async function save() {
    const pending = page.waitForResponse(
      (r) => ['POST', 'PATCH'].includes(r.request().method()) && r.url().includes('/api/'),
    )
    await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
    const response = await pending
    expect(response.status(), await response.text()).toBeLessThan(300)
    await expect(page.getByRole('dialog')).not.toBeVisible()
  }
  await page.goto('/erp/masterdata')
  await page.getByRole('button', { name: '新增往来单位', exact: true }).click()
  await page.getByRole('dialog').getByLabel('单位名称', { exact: true }).fill(customer)
  await page.getByRole('dialog').getByLabel('类型', { exact: true }).selectOption('customer')
  await save()
  await page.goto('/erp/projects')
  await page.getByRole('button', { name: '新建项目', exact: true }).click()
  await page.getByRole('dialog').getByLabel('项目名称', { exact: true }).fill(project)
  const select = page.getByRole('dialog').getByLabel('客户', { exact: true })
  await select.selectOption(
    (await select.locator('option').filter({ hasText: customer }).getAttribute('value'))!,
  )
  await page.getByRole('dialog').getByLabel('负责人', { exact: true }).selectOption('1')
  await page.getByRole('dialog').getByLabel('项目成员', { exact: true }).selectOption('1')
  await save()
  await page.getByRole('link', { name: project, exact: true }).click()
  await expect(page).toHaveURL(/\/projects\/\d+$/)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  await page.getByRole('tab', { name: '附件', exact: true }).click()
  await page.getByRole('button', { name: '上传附件', exact: true }).click()
  const d = page.getByRole('dialog')
  await d.getByLabel('分类', { exact: true }).selectOption('contract')
  const name = '合同验证-' + Date.now() + '.txt'
  const content = '受保护的合同附件：保存与下载内容必须一致。'
  await d
    .getByLabel('文件', { exact: true })
    .setInputFiles({ name, mimeType: 'text/plain', buffer: Buffer.from(content) })
  const response = page.waitForResponse(
    (r) => r.url().endsWith('/documents/') && r.request().method() === 'POST',
  )
  await d.getByRole('button', { name: '保存', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  await expect(d).not.toBeVisible()
  const row = page.locator('.el-table__body tr:visible').filter({ hasText: name })
  await row.getByRole('button', { name: '操作 ▾', exact: true }).click()
  const pending = page.waitForEvent('download')
  await page.getByRole('menuitem', { name: '下载', exact: true }).click()
  const download = await pending
  expect(download.suggestedFilename()).toBe(name)
  const path = info.outputPath(name)
  await download.saveAs(path)
  expect(await readFile(path, 'utf8')).toBe(content)
  const id = (await result.json()).id
  const anonymous = await page.request.get(`/api/business/documents/${id}/download/`)
  expect(anonymous.status()).toBe(403)
  expect(anonymous.headers()['content-type']).toContain('application/json')
  const publicFile = await page.request.get('/media/' + name)
  expect(publicFile.status()).toBe(404)
  const allowed = await page.request.get(`/api/business/documents/${id}/download/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(allowed.status()).toBe(200)
  expect(allowed.headers()['cache-control']).toContain('no-store')
  expect(await allowed.text()).toBe(content)
})
