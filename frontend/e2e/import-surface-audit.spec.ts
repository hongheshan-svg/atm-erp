import { readFile } from 'node:fs/promises'
import { test, expect, login, expectHttpError } from './fixtures'

test('十二种批量导入入口的模板字段、页面映射和错误文件处理', async ({ page }, info) => {
  test.setTimeout(180000)
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const projects = await page.request.get('/api/business/projects/', { headers })
  expect(projects.status()).toBe(200)
  const projectId = (await projects.json()).results[0]?.id
  expect(projectId, '隔离业务链应已创建项目').toBeTruthy()
  const cases = [
    ['items', 'masterdata?section=items'], ['partners', 'masterdata?section=partners'],
    ['sales', 'sales'], ['projects', 'projects'], ['purchases', 'purchases'],
    ['stocks', 'inventory?section=stocks'], ['moves', 'inventory?section=moves'],
    ['entries', 'finance?section=entries'], ['payments', 'finance?section=payments'],
    ['tasks', `projects/${projectId}?tab=tasks&section=tasks`],
    ['time', `projects/${projectId}?tab=tasks&section=time`],
    ['deliveries', `projects/${projectId}?tab=deliveries&section=deliveries`],
  ]
  const evidence: Record<string, unknown>[] = []
  for (const [resource, route] of cases) {
    await page.goto(`/erp/${route}`)
    await page.getByLabel('导入导出格式').selectOption('csv')
    await page.getByRole('button', { name: '导入', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
    await dialog.getByText('模板字段与页面列对应说明', { exact: true }).click()
    const fieldLabels = dialog.locator('.import-field-guide .el-table__body tr td:first-child')
    await expect(fieldLabels.first()).toBeVisible()
    const labels = (await fieldLabels.allTextContents()).map(s => s.trim())
    expect(labels.length).toBeGreaterThan(0)
    const downloading = page.waitForEvent('download')
    await dialog.getByRole('button', { name: '下载模板', exact: true }).click()
    const file = await downloading
    expect(file.suggestedFilename()).toBe(`${resource}-template.csv`)
    const content = (await readFile((await file.path())!, 'utf8')).replace(/^\uFEFF/, '').trim()
    expect(content.split(',')).toEqual(labels)
    expect(new Set(labels).size).toBe(labels.length)
    const stopExpected = expectHttpError(page, `/api/business/${resource}/import-file/`, 400)
    await dialog.locator('input[type=file]').setInputFiles({ name: 'wrong-header.csv', mimeType: 'text/csv', buffer: Buffer.from('错误表头\n不可入库的数据') })
    await expect(dialog.getByRole('alert')).toContainText('表头必须依次为')
    await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
    stopExpected()
    evidence.push({ resource, templateHeaders: labels, invalidHeaderRejected: true })
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog).toBeHidden()
    await page.getByRole('button', { name: '导入', exact: true }).click()
    await expect(dialog.getByRole('alert')).toHaveCount(0)
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  }
  await info.attach('import-surface-inventory', { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' })
})

test('关闭未确认的导入后重新打开，不应继续提交上次文件', async ({ page }) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/masterdata?section=items')
  await page.getByRole('button', { name: '导入', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  const code = `CANCEL${Date.now()}`
  await dialog.locator('input[type=file]').setInputFiles({ name: 'cancel.csv', mimeType: 'text/csv', buffer: Buffer.from(`物料编码,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位,独立建码原因\n${code},取消导入验收,规格,,,21,品牌,标准件,台,`) })
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  await page.getByRole('button', { name: '导入', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '下载模板', exact: true })).toBeEnabled()
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await expect(dialog.getByText('共 1 条，确认时再次校验', { exact: false })).toHaveCount(0)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const list = await page.request.get(`/api/business/items/?search=${code}`, { headers: { Authorization: `Bearer ${token}` } })
  expect(list.status()).toBe(200)
  expect((await list.json()).count).toBe(0)
})

test('项目筛选提示随选中和清空同步变化', async ({ page }) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  for (const route of ['bom', 'finance']) {
    await page.goto(`/erp/${route}`)
    const select = page.getByRole('combobox', { name: '项目筛选', exact: true })
    const hint = page.locator('.project-filter > small')
    await select.selectOption('')
    await expect(hint).toHaveText(route === 'bom' ? '请选择项目' : '未选择时显示全部项目')
    const choice = select.locator('option').nth(1)
    await expect(choice).toBeAttached()
    await select.selectOption((await choice.getAttribute('value'))!)
    await expect(hint).toHaveText('仅显示所选项目')
    await select.selectOption('')
    await expect(hint).toHaveText(route === 'bom' ? '请选择项目' : '未选择时显示全部项目')
  }
})

test('导入类型填错逐行提示，夹在错误行之间的有效记录也不入库', async ({ page }) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/masterdata?section=partners')
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const schema = await page.request.get('/api/business/partners/import-schema/', { headers })
  expect(schema.status()).toBe(200)
  const columns: { key: string; label: string }[] = (await schema.json()).columns
  const name = `逐行校验${Date.now()}`
  const lines = ['错误类型', 'customer', '另一错误类型'].map((kind, index) => {
    const data: Record<string, string> = { name: `${name}-${index}`, kind, payment_term: 'manual' }
    return columns.map(c => data[c.key] || '').join(',')
  })
  await page.getByRole('button', { name: '导入', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  const pending = page.waitForResponse(r => r.url().endsWith('/partners/import-file/') && r.request().method() === 'POST')
  await dialog.locator('input[type=file]').setInputFiles({ name: 'invalid-kind.csv', mimeType: 'text/csv', buffer: Buffer.from([columns.map(c => c.label).join(','), ...lines].join('\n')) })
  const preview = await pending
  expect(preview.status()).toBe(200)
  expect((await preview.json()).errors.map((e: { row: number }) => e.row)).toEqual([2, 4])
  await expect(dialog.locator('.import-errors')).toContainText('第 2 行')
  await expect(dialog.locator('.import-errors')).toContainText('第 4 行')
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  const records = await page.request.get(`/api/business/partners/?search=${name}`, { headers })
  expect(records.status()).toBe(200)
  expect((await records.json()).count).toBe(0)
})
