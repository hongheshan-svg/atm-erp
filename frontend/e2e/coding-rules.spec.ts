import { test, expect, login, openRowAction } from './fixtures'

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
  async function configure(values: Record<string, unknown>, reason: string) {
    const latest = await projectRule()
    const response = await page.request.post(`/api/core/codes/${latest.id}/configure/`, {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
      data: { ...values, reason, expected_revision: latest.revision },
    })
    expect(response.ok(), await response.text()).toBe(true)
  }
  const before = await projectRule()
  const original = { prefix: before.prefix, date_format: before.date_format, padding: before.padding, reset_cycle: before.reset_cycle }
  try {
    await configure({ prefix: before.prefix === 'QA' ? 'QB' : 'QA', date_format: 'YY', padding: 2, reset_cycle: 'year' }, '隔离测试旧配置切换')
    await page.goto('/erp/settings?section=codes')
    const guide = page.getByRole('region', { name: '设备命名与编码规范' })
    await expect(guide).toContainText('按销售合同中的设备 / 产线名称原文填写')
    await guide.getByText('查看八类物料编码与工程图号').click()
    await expect(guide).toContainText('2199000001')
    await guide.screenshot({ path: info.outputPath('coding-rules.png'), animations: 'disabled' })
    // 用途格是打开详情的按钮；手机窄屏把前缀、日期格式等并进同一格的副行，按按钮名称定位这一行。
    const row = page.getByRole('region', { name: '编号规则', exact: true }).getByRole('row').filter({ has: page.getByRole('button', { name: '项目', exact: true }) })
    await openRowAction(page, row, '应用项目规范')
    const dialog = page.getByRole('dialog', { name: '应用项目编号规范' })
    await dialog.getByLabel('应用原因').fill('按QP-001执行')
    await dialog.locator('button[type="submit"]').click()
    await expect(dialog).not.toBeVisible()
    const after = await projectRule()
    expect(after).toMatchObject({ prefix: 'ATM', date_format: 'YY', padding: 2, reset_cycle: 'year', counter: before.counter })
    await page.goto('/erp/projects')
    await page.getByRole('button', { name: '新建项目', exact: true }).click()
    await expect(page.getByPlaceholder('按销售合同中的设备 / 产线名称原文填写')).toBeVisible()
  } finally {
    // 项目编号规则是全安装共用的：恢复用例前的配置（流水号不回退），后续用例不受本用例影响。
    const latest = await projectRule()
    if (Object.entries(original).some(([key, value]) => latest[key] !== value)) await configure(original, '隔离测试恢复原项目编号规则')
  }
})
