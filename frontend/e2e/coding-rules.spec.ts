import { test, expect, login } from './fixtures'

test('合同设备命名说明与项目编号规范应用保留流水', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  async function projectRule() {
    const response = await page.request.get('/api/core/codes/', { headers })
    expect(response.ok()).toBe(true)
    const data = await response.json()
    return (data.results ?? data).find((r: { key: string }) => r.key === 'project')
  }
  const before = await projectRule()
  const configure = await page.request.post(`/api/core/codes/${before.id}/configure/`, {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
    data: { prefix: before.prefix === 'QA' ? 'QB' : 'QA', date_format: 'YY', padding: 2, reset_cycle: 'year', reason: '隔离测试旧配置切换', expected_revision: before.revision },
  })
  expect(configure.ok(), await configure.text()).toBe(true)
  await page.goto('/erp/settings?section=codes')
  const guide = page.getByRole('region', { name: '设备命名与编码规范' })
  await expect(guide).toContainText('按销售合同中的设备 / 产线名称原文填写')
  await guide.getByText('查看八类物料编码与工程图号').click()
  await expect(guide).toContainText('2199000001')
  await guide.screenshot({ path: info.outputPath('coding-rules.png'), animations: 'disabled' })
  const row = page.getByRole('row').filter({ has: page.getByRole('cell', { name: '项目', exact: true }) })
  await row.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByText('应用项目规范', { exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '应用项目编号规范' })
  await dialog.getByLabel('应用原因').fill('按QP-001执行')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  const after = await projectRule()
  expect(after).toMatchObject({ prefix: 'ATM', date_format: 'YY', padding: 2, reset_cycle: 'year', counter: before.counter })
  await page.goto('/erp/projects')
  await page.getByRole('button', { name: '新建项目', exact: true }).click()
  await expect(page.getByPlaceholder('按销售合同中的设备 / 产线名称原文填写')).toBeVisible()
})
