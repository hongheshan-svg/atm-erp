import { test, expect, login, openImport, expectHttpError } from './fixtures'

test('真实导入：项目上下文、字段纠错、确认重验、内容去重及准确结果入口', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = `${info.project.name}-${Date.now()}`
  async function get(path: string) {
    const response = await page.request.get(`/api/${path}`, { headers })
    expect(response.status(), await response.text()).toBe(200)
    return response.json()
  }
  async function post(path: string, data: Record<string, unknown>, status = 201) {
    const response = await page.request.post(`/api/${path}`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBe(status)
    return response.json()
  }
  const actor = await get('auth/me/')
  const customer = await post('business/partners/', { name: `导入验证客户${suffix}`, kind: 'customer' })
  const createdProject = await post('business/projects/', { name: `导入验证项目${suffix}`, customer: customer.id, manager: actor.id })
  const project = await get(`business/projects/${createdProject.id}/`)
  const task = await post('business/tasks/', { project: project.id, kind: 'design', title: '导入工时任务', assignee: actor.id })
  const now = new Date()
  const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-')
  async function preview(resource: string, row: Record<string, unknown>, filename: string) {
    const schema = await get(`business/${resource}/import-schema/`)
    const csv = [schema.columns.map((column: { label: string }) => column.label), schema.columns.map((column: { key: string }) => row[column.key] ?? '')]
      .map(values => values.map((value: unknown) => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\n')
    const response = page.waitForResponse(r => r.url().endsWith(`/${resource}/import-file/`) && r.request().method() === 'POST')
    const input = page.getByRole('dialog').filter({ has: page.locator('input[type=file]') }).locator('input[type=file]')
    await expect(input).toBeEnabled()
    await input.setInputFiles({ name: filename, mimeType: 'text/csv', buffer: Buffer.from(csv) })
    const received = await response
    expect(received.status(), await received.text()).toBe(200)
    return received.json()
  }

  await page.goto(`/erp/projects/${project.id}?tab=tasks&section=time`)
  await openImport(page)
  let dialog = page.getByRole('dialog', { name: '导入工时', exact: true })
  await expect(dialog.locator('.import-context')).toContainText(`${project.name}（${project.code}）`)
  await page.screenshot({ path: info.outputPath('real-time-project-context.png'), animations: 'disabled' })
  const timeRow = { task: '999999999', date: today, hours: '1', reason: '真实导入验证' }
  const invalid = await preview('time', timeRow, '工时待修正.csv')
  expect(invalid.can_import).toBe(false)
  expect(invalid.errors[0].fields).toEqual(['task'])
  await expect(dialog.locator('.import-errors')).toContainText('任务ID')
  await dialog.getByRole('button', { name: '定位第 2 行', exact: true }).click()
  await expect(dialog.locator('[data-import-row="2"][data-import-field="task"]')).toBeFocused()
  await expect(dialog.locator('[data-import-row="2"][data-import-field="task"]')).toBeInViewport({ ratio: 1 })
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await page.screenshot({ path: info.outputPath('real-time-context-field-error.png'), animations: 'disabled' })
  const validTime = await preview('time', { ...timeRow, task: String(task.id) }, '工时.csv')
  expect(validTime.can_import).toBe(true)
  expect((await get(`business/time/?task__project=${project.id}`)).count).toBe(0)
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(dialog.getByRole('status')).toContainText('成功导入 1 条记录')
  expect((await get(`business/time/?task__project=${project.id}`)).count).toBe(1)
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()

  const expense = await post('business/entries/expense/', { project: project.id, title: '确认阶段重验费用', amount: '20', due_date: today })
  await page.goto(`/erp/projects/${project.id}?tab=finance&section=payments`)
  await openImport(page)
  dialog = page.getByRole('dialog', { name: '导入收付款记录', exact: true })
  await expect(dialog.locator('.import-context')).toContainText(project.code)
  expect((await preview('payments', { entry: expense.id, amount: '10', date: today, reason: '待确认付款' }, '付款.csv')).can_import).toBe(true)
  await post(`business/entries/${expense.id}/pay/`, { amount: '20', date: today, reason: '预览期间款项已付清' }, 200)
  expectHttpError(page, '/api/business/payments/import-confirm/', 400)
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(dialog).toContainText('数据已变化')
  await expect(dialog.locator('.import-errors')).toContainText('未结余额')
  await expect(dialog.locator('.import-feedback-start')).toBeInViewport({ ratio: 1 })
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: '下载标注错误的 Excel', exact: true })).toBeVisible()
  expect((await get(`business/payments/?entry__project=${project.id}`)).count).toBe(1)
  await page.screenshot({ path: info.outputPath('real-confirmation-error.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()

  await page.goto(`/erp/finance?section=entries&project=${project.id}`)
  await openImport(page)
  dialog = page.getByRole('dialog', { name: '导入项目费用', exact: true })
  await expect(dialog.locator('.import-context')).toContainText(project.code)
  const expenseRow = { project: project.code, title: `去重费用${suffix}`, amount: '12.00', due_date: today }
  expect((await preview('entries', expenseRow, '费用.csv')).duplicate_import).toBeNull()
  const confirmation = page.waitForResponse(r => r.url().endsWith('/entries/import-confirm/') && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  const response = await confirmation
  expect(response.status(), await response.text()).toBe(200)
  const saved = await response.json()
  await expect(dialog.getByRole('status')).toBeInViewport({ ratio: 1 })
  await expect(dialog.getByRole('link', { name: '查看导入记录', exact: true })).toHaveAttribute('href', new RegExp(`focus=${saved.results[0].id}`))
  await page.screenshot({ path: info.outputPath('real-import-success.png'), animations: 'disabled' })
  await dialog.getByRole('link', { name: '查看导入记录', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`focus=${saved.results[0].id}`))
  await expect(page.locator('.action-form')).toContainText(expenseRow.title)
  expect((await get(`business/entries/${saved.results[0].id}/`)).title).toBe(expenseRow.title)

  await page.goto(`/erp/finance?section=entries&project=${project.id}`)
  await openImport(page)
  dialog = page.getByRole('dialog', { name: '导入项目费用', exact: true })
  expect((await preview('entries', { ...expenseRow, amount: '12.0' }, '改名后的费用.csv')).duplicate_import).toBeTruthy()
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await expect(dialog.locator('.import-duplicate')).toContainText('相同业务归属和内容已成功导入')
  await dialog.locator('.import-duplicate').scrollIntoViewIfNeeded()
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width + 1)
  await page.screenshot({ path: info.outputPath('real-duplicate-confirmation.png'), animations: 'disabled' })
  await dialog.getByLabel('我已核对现有记录，确认再次导入并新增相同内容', { exact: true }).check()
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(dialog.getByRole('status')).toContainText('成功导入 1 条记录')
  expect((await get(`business/entries/?project=${project.id}&search=${encodeURIComponent(expenseRow.title)}`)).count).toBe(2)
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '导入导出 ▾', exact: true }).click()
  const downloading = page.waitForEvent('download')
  await page.getByRole('menuitem', { name: '导出 Excel', exact: true }).click()
  expect((await downloading).suggestedFilename()).toMatch(/^应收应付与费用导出_\d{4}-\d{2}-\d{2}\.xlsx$/)
})

test('生产经理真实批量导入仅接受参与项目的装配调试，混入设计整批拒绝', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const adminHeaders = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() }
  const suffix = `${info.project.name}-${Date.now()}`
  const username = `production-import-${suffix}`
  const password = 'Import-Production-Isolated-2026'
  async function create(path: string, data: Record<string, unknown>) {
    const response = await page.request.post(`/api/${path}/`, { headers: { ...adminHeaders, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBe(201)
    return response.json()
  }
  const me = await page.request.get('/api/auth/me/', { headers: adminHeaders })
  const admin = await me.json()
  const producer = await create('auth/users', { username, display_name: '导入验证生产经理', roles: ['production_manager', 'purchaser'], password })
  const customer = await create('business/partners', { name: `生产导入客户${suffix}`, kind: 'customer' })
  const project = await create('business/projects', { name: `生产导入项目${suffix}`, customer: customer.id, manager: admin.id, members: [producer.id] })
  const detail = await page.request.get(`/api/business/projects/${project.id}/`, { headers: adminHeaders })
  const code = (await detail.json()).code
  await page.evaluate(() => localStorage.clear())
  await login(page, username, password)
  await page.goto(`/erp/projects/${project.id}?tab=tasks&section=tasks`)
  await openImport(page)
  const dialog = page.getByRole('dialog', { name: '导入项目任务', exact: true })
  await expect(dialog).toContainText('生产经理仅可导入本人参与项目的装配、调试任务')
  async function upload(stage: string) {
    const response = page.waitForResponse(r => r.url().endsWith('/tasks/import-file/') && r.request().method() === 'POST')
    await expect(dialog.locator('input[type=file]')).toBeEnabled()
    await dialog.locator('input[type=file]').setInputFiles({ name: '生产任务.csv', mimeType: 'text/csv',
      buffer: Buffer.from(`任务名称,阶段,执行人姓名或账号,期限,项目编号,说明\n装配任务,装配,${username},,${code},\n第二项任务,${stage},${username},,${code},`) })
    const result = await response
    expect(result.status(), await result.text()).toBe(200)
    return result.json()
  }
  const denied = await upload('设计')
  expect(denied.can_import).toBe(false)
  expect(denied.errors[0].row).toBe(3)
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  const before = await page.request.get(`/api/business/tasks/?project=${project.id}`, { headers: adminHeaders })
  expect((await before.json()).count).toBe(0)
  await dialog.locator('.import-errors').scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('real-production-design-rejected.png'), animations: 'disabled' })
  expect((await upload('调试')).can_import).toBe(true)
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(dialog.getByRole('status')).toContainText('成功导入 2 条记录')
  await expect(dialog.getByRole('status')).toBeInViewport({ ratio: 1 })
  const after = await page.request.get(`/api/business/tasks/?project=${project.id}`, { headers: adminHeaders })
  const tasks = await after.json()
  expect(tasks.count).toBe(2)
  expect(tasks.results.map((task: { kind: string }) => task.kind).sort()).toEqual(['assembly', 'test'])
  await page.screenshot({ path: info.outputPath('real-production-import-success.png'), animations: 'disabled' })

  await test.step('真实 HTTP：经理降为生产经理后，同操作键的旧设计凭据拒绝，装配凭据仍可重试', async () => {
    async function setRoles(roles: string[]) {
      const response = await page.request.patch(`/api/auth/users/${producer.id}/`, { headers: adminHeaders, data: { roles } })
      expect(response.status(), await response.text()).toBe(200)
    }
    const producerToken = await page.evaluate(() => localStorage.getItem('access_token'))
    const producerHeaders = { Authorization: `Bearer ${producerToken}` }
    async function confirm(token: string, key: string) {
      return page.request.post('/api/business/tasks/import-confirm/', {
        headers: { ...producerHeaders, 'Idempotency-Key': key }, data: { token },
      })
    }
    await setRoles(['manager', 'purchaser'])
    const completed: { kind: string; token: string; key: string; result: unknown }[] = []
    for (const kind of ['设计', '装配']) {
      const preview = await page.request.post('/api/business/tasks/import-file/', {
        headers: producerHeaders,
        multipart: { file: { name: '旧凭据.csv', mimeType: 'text/csv',
          buffer: Buffer.from(`任务名称,阶段,执行人姓名或账号,期限,项目编号,说明\n旧凭据${kind},${kind},${username},,${code},岗位调整重放验证`) } },
      })
      expect(preview.status(), await preview.text()).toBe(200)
      const data = await preview.json()
      expect(data.can_import).toBe(true)
      const key = crypto.randomUUID()
      const saved = await confirm(data.token, key)
      expect(saved.status(), await saved.text()).toBe(200)
      completed.push({ kind, token: data.token, key, result: await saved.json() })
    }
    await setRoles(['production_manager', 'purchaser'])
    for (const saved of completed) {
      for (const key of [saved.key, crypto.randomUUID()]) {
        const replay = await confirm(saved.token, key)
        expect(replay.status(), await replay.text()).toBe(saved.kind === '设计' ? 403 : 200)
        if (saved.kind === '装配') expect(await replay.json()).toEqual(saved.result)
      }
    }
    const unchanged = await page.request.get(`/api/business/tasks/?project=${project.id}`, { headers: adminHeaders })
    expect((await unchanged.json()).count).toBe(4)
  })
})
