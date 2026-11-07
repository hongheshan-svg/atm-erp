import { test, expect, login, openRowAction } from './fixtures'

test('项目六阶段模板支持一键生成、并行任务、日期调整和增删节点', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const get = async (path: string) => {
    const response = await page.request.get('/api/' + path, { headers })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const post = async (path: string, data: object) => {
    const response = await page.request.post('/api/business/' + path, {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data,
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const today = new Date().toISOString().slice(0, 10)
  const name = '六阶段里程碑验收-' + Date.now() + '-' + info.project.name
  const me = await get('auth/me/')
  const customer = await post('partners/', { name, kind: 'customer' })
  const sale = await post('sales/', { name, customer: customer.id, manager: me.id })
  await post('sales/' + sale.id + '/quote/', { amount: '100', reason: '隔离验证' })
  const signed = await post('sales/' + sale.id + '/sign/', {
    date: today, manager: me.id, milestones: [{ title: '合同款', amount: '100', due_date: today }],
  })
  const project = signed.project
  await post('tasks/', { project, kind: 'design', title: '原有任务保留', assignee: me.id })
  await page.goto('/erp/projects/' + project + '?tab=tasks&section=tasks')
  const overview = page.getByRole('region', { name: '项目六阶段里程碑' })
  await expect(overview.locator('.phase-card')).toHaveCount(6)
  await overview.getByRole('button', { name: '一键生成里程碑' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('项目里程碑 · 20 行')
  await dialog.getByLabel('截止日期', { exact: true }).first().fill('2026-12-20')
  await page.screenshot({ path: info.outputPath('milestone-template.png'), animations: 'disabled' })
  const generated = page.waitForResponse(response => response.url().includes('/tasks/apply-milestones/') && response.request().method() === 'POST')
  await dialog.getByRole('button', { name: '确认生成里程碑', exact: true }).click()
  expect((await generated).status()).toBe(201)
  await expect(dialog).toHaveCount(0)
  let tasks = (await get('business/tasks/?project=' + project + '&page_size=100')).results
  expect(tasks).toHaveLength(21)
  expect(tasks.find((row: any) => row.milestone === 'design_3d').due_date).toBe('2026-12-20')
  expect(tasks.filter((row: any) => row.system_managed)).toHaveLength(3)
  await expect(overview.getByRole('button', { name: /设计阶段/ })).toContainText('0 / 7')
  await overview.getByRole('button', { name: /采购阶段/ }).click()
  const row = page.locator('.el-table__body tr:visible').filter({ hasText: '长交期' })
  await expect(row).toHaveCount(1)
  await openRowAction(page, row, '重新分配')
  await dialog.getByLabel('截止日期', { exact: true }).fill('2026-12-18')
  await dialog.getByLabel('原因 / 说明', { exact: true }).fill('关键采购计划调整')
  await dialog.locator('button[type="submit"]').click()
  await expect(dialog).toHaveCount(0)
  await expect(row).toContainText('2026-12-18')
  await openRowAction(page, row, '完成任务')
  await dialog.getByLabel('原因 / 说明', { exact: true }).fill('长交期先行，设计仍在进行')
  await dialog.locator('button[type="submit"]').click()
  await expect(dialog).toHaveCount(0)
  await expect(overview.getByRole('button', { name: /采购阶段/ })).toContainText('1 / 3')
  tasks = (await get('business/tasks/?project=' + project + '&page_size=100')).results
  expect(tasks.find((row: any) => row.milestone === 'design_3d').status).toBe('open')
  await overview.getByRole('button', { name: '一键生成里程碑' }).click()
  await expect(dialog).toContainText('项目里程碑 · 0 行')
  await dialog.getByRole('button', { name: '添加行', exact: true }).click()
  await dialog.getByLabel('阶段', { exact: true }).selectOption('site')
  await dialog.getByLabel('任务名称', { exact: true }).fill('客户操作培训')
  await dialog.getByLabel('执行人', { exact: true }).selectOption(String(me.id))
  await dialog.getByRole('button', { name: '确认生成里程碑', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await overview.getByRole('button', { name: /客户终验收阶段/ }).click()
  const training = page.locator('.el-table__body tr:visible').filter({ hasText: '客户操作培训' })
  await expect(training).toHaveCount(1)
  await openRowAction(page, training, '取消任务')
  await dialog.getByLabel('原因 / 说明', { exact: true }).fill('本项目无需单独培训节点')
  await dialog.locator('button[type="submit"]').click()
  await expect(dialog).toHaveCount(0)
  await expect(overview.getByRole('button', { name: /客户终验收阶段/ })).toContainText('0 / 3')
  await overview.getByRole('button', { name: '查看全部阶段' }).click()
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
  await expect(page.locator('.el-message:visible')).toHaveCount(0)
  await overview.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('milestone-overview.png'), animations: 'disabled' })
})
