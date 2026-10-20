import { readFile } from 'node:fs/promises'
import { test, expect, login, expectHttpError, openImport } from './fixtures'

test('人员可按姓名选择并导入，重名明确账号', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const me = await page.request.get('/api/auth/me/', { headers })
  expect(me.status()).toBe(200)
  const actor = await me.json()
  const suffix = Date.now()
  const displayName = `吴兴广${suffix}`
  const username = `wuxingguang_${suffix}`
  async function create(path: string, data: Record<string, unknown>) {
    const response = await page.request.post(`/api/${path}/`, {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data,
    })
    expect(response.status(), await response.text()).toBe(201)
    return response.json()
  }
  const member = await create('auth/users', {
    username, display_name: displayName, roles: ['member'], password: 'Isolated-person-name-2026-only',
  })
  const partner = await create('business/partners', { name: `姓名导入客户${suffix}`, kind: 'customer' })
  const project = await create('business/projects', {
    name: `姓名导入项目${suffix}`, customer: partner.id, manager: actor.id, members: [member.id],
  })
  const projectResponse = await page.request.get(`/api/business/projects/${project.id}/`, { headers })
  expect(projectResponse.status()).toBe(200)
  const projectCode = (await projectResponse.json()).code
  async function savedTasks() {
    const response = await page.request.get(`/api/business/tasks/?project=${project.id}`, { headers })
    expect(response.status()).toBe(200)
    return (await response.json()).results as { assignee: number; title: string }[]
  }

  await page.goto(`/erp/projects/${project.id}?tab=tasks&section=tasks`)
  await page.getByRole('button', { name: '新建任务', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新建任务', exact: true })
  await form.getByLabel('阶段', { exact: true }).selectOption('design')
  await form.getByLabel('任务名称', { exact: true }).fill('按姓名选择执行人')
  await form.getByLabel('执行人', { exact: true }).selectOption({ label: `${displayName}（${username}）` })
  await expect(form.getByLabel('执行人', { exact: true })).toHaveValue(String(member.id))
  await form.getByLabel('执行人', { exact: true }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('person-name-selection.png'), animations: 'disabled' })
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form).toBeHidden()
  expect(await savedTasks()).toEqual([expect.objectContaining({ title: '按姓名选择执行人', assignee: member.id })])

  await openImport(page)
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  const confirm = dialog.getByRole('button', { name: '确认导入', exact: true })
  async function preview(title: string, person: string) {
    const response = page.waitForResponse(r => r.url().endsWith('/tasks/import-file/') && r.request().method() === 'POST')
    await dialog.locator('input[type="file"]').setInputFiles({
      name: 'tasks.csv', mimeType: 'text/csv',
      buffer: Buffer.from(`任务名称,阶段,执行人姓名或账号,期限,项目编号,说明\n${title},设计,${person},,${projectCode},`),
    })
    expect((await response).status()).toBe(200)
  }
  await preview('直接填写姓名导入', displayName)
  await expect(confirm).toBeEnabled()
  // 预览没有写入；确认后仍指向姓名对应的唯一人员。
  expect(await savedTasks()).toHaveLength(1)
  await confirm.click()
  await expect(dialog.getByRole('status')).toContainText('成功导入 1 条记录')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(await savedTasks()).toEqual(expect.arrayContaining([
    expect.objectContaining({ title: '直接填写姓名导入', assignee: member.id }),
  ]))

  await create('auth/users', {
    username: `tongming_${suffix}`, display_name: displayName, roles: ['member'], password: 'Isolated-person-name-2026-only',
  })
  await openImport(page)
  await preview('重名明确账号导入', displayName)
  const errors = dialog.locator('.import-errors')
  await expect(errors).toContainText('对应多名人员')
  await expect(errors).toContainText('姓名（用户名）')
  await expect(confirm).toBeDisabled()
  expect(await savedTasks()).toHaveLength(2)
  await errors.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('person-name-ambiguity.png'), animations: 'disabled' })
  await preview('重名明确账号导入', `${displayName}（${username}）`)
  await expect(confirm).toBeEnabled()
  await confirm.click()
  await expect(dialog.getByRole('status')).toContainText('成功导入 1 条记录')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  const tasks = await savedTasks()
  expect(tasks).toHaveLength(3)
  expect(tasks.every(task => task.assignee === member.id)).toBe(true)
})

test('任务与BOM导入错误显示中文字段和文件行号', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const me = await page.request.get('/api/auth/me/', { headers })
  expect(me.status()).toBe(200)
  const actor = await me.json()
  const suffix = Date.now()
  async function create(resource: string, data: Record<string, unknown>) {
    const response = await page.request.post(`/api/business/${resource}/`, {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data,
    })
    expect(response.status(), await response.text()).toBe(201)
    return response.json()
  }
  const partner = await create('partners', { name: `中文提示客户${suffix}`, kind: 'customer' })
  const project = await create('projects', { name: `中文提示项目${suffix}`, customer: partner.id, manager: actor.id })
  const projectResponse = await page.request.get(`/api/business/projects/${project.id}/`, { headers })
  expect(projectResponse.status()).toBe(200)
  const projectCode = (await projectResponse.json()).code
  const itemCode = `ZH${suffix}`
  await create('items', { code: itemCode, name: `中文提示验证物料${suffix}`, specification: '测试规格', unit: '件' })

  await page.goto(`/erp/projects/${project.id}?tab=tasks&section=tasks`)
  await openImport(page)
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  await expect(dialog.locator('input[type="file"]')).toBeEnabled()
  const tasks = [
    '任务名称,阶段,执行人账号,期限,项目编号,说明',
    `检查账号,设计,不存在的登录账号,2026-10-20,${projectCode},`,
    `检查日期,设计,${actor.username},20,${projectCode},`,
    `检查阶段,T0,${actor.username},2026-10-20,${projectCode},`,
  ].join('\n')
  await dialog.locator('input[type="file"]').setInputFiles({ name: 'tasks.csv', mimeType: 'text/csv', buffer: Buffer.from(tasks) })
  const errors = dialog.locator('.import-errors')
  await expect(errors).toContainText('第 2 行：未找到人员')
  await expect(errors).toContainText('第 3 行：期限：')
  await expect(errors).toContainText('第 4 行：阶段：')
  await expect(errors).not.toContainText('due_date')
  await expect(errors).not.toContainText('kind')
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await errors.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('task-chinese-errors.png'), animations: 'disabled' })

  await page.goto('/erp/bom')
  await page.getByRole('combobox', { name: '项目筛选', exact: true }).selectOption(String(project.id))
  const upload = page.locator('input[type="file"]')
  await expect(upload).toBeEnabled()
  await upload.setInputFiles({ name: 'bom.csv', mimeType: 'text/csv', buffer: Buffer.from(`物料编码,数量,变更说明\n${itemCode},错误,检查数量`) })
  const bomErrors = page.locator('.import-preview [role="alert"]')
  await expect(bomErrors).toContainText('第 2 行：数量：')
  await expect(bomErrors).not.toContainText('quantity')
  await expect(bomErrors).not.toContainText('"message"')
  await bomErrors.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('bom-chinese-errors.png'), animations: 'disabled' })
  const tasksResponse = await page.request.get(`/api/business/tasks/?project=${project.id}`, { headers })
  expect(tasksResponse.status()).toBe(200)
  expect((await tasksResponse.json()).count).toBe(0)
})

test('BOM选择文件后直接显示预览、错误和确认入口，修正后实际导入', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const me = await page.request.get('/api/auth/me/', { headers })
  expect(me.status()).toBe(200)
  const actor = await me.json()
  const suffix = Date.now()
  async function create(resource: string, data: Record<string, unknown>) {
    const response = await page.request.post(`/api/business/${resource}/`, {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data,
    })
    expect(response.status(), await response.text()).toBe(201)
    return response.json()
  }
  const customer = await create('partners', { name: `预览修复客户${suffix}`, kind: 'customer' })
  const project = await create('projects', { name: `预览修复项目${suffix}`, customer: customer.id, manager: actor.id })
  async function demand() {
    const response = await page.request.get(`/api/business/projects/${project.id}/demand/`, { headers })
    expect(response.status()).toBe(200)
    return response.json()
  }
  await page.goto('/erp/bom')
  await page.getByRole('combobox', { name: '项目筛选', exact: true }).selectOption(String(project.id))
  const upload = page.locator('input[type="file"]')
  const dialog = page.getByRole('dialog', { name: 'BOM 导入预览', exact: true })
  const confirm = dialog.getByRole('button', { name: '确认导入', exact: true })
  const columns = '物料编码,单元,需求数量,变更说明,需求日期,申请日期,申请人,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位'
  const name = `预览测试滑块${suffix}`
  const goodRow = ['', '机械手', '4', '', '2026-09-25', '2026-09-10', '吴兴广', name, 'HGW20CC', '', '', '无图·标准件', '上银', '标准件', 'PCS']
  const badRow = [...goodRow]
  badRow[11] = '无图标准件'
  async function uploadRows(rows: string[][]) {
    await upload.setInputFiles({
      name: 'bom.csv', mimeType: 'text/csv',
      buffer: Buffer.from([columns, ...rows.map(row => row.join(','))].join('\n')),
    })
  }
  // 足量明细验证错误区域滚动时，确认入口仍在视口内。
  await uploadRows(Array.from({ length: 120 }, () => badRow))
  await expect(dialog.getByRole('status')).toContainText('校验未通过')
  await expect(dialog.locator('.import-errors')).toContainText('第 121 行：产品编码类别')
  await expect(dialog.getByText(name, { exact: true }).first()).toBeVisible()
  await expect(confirm).toBeDisabled()
  await expect(confirm).toBeInViewport()
  await expect(dialog.locator('.import-errors')).toBeInViewport()
  const box = (await dialog.locator('.el-dialog').boundingBox())!
  expect(box.x).toBeGreaterThanOrEqual(0)
  expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1)
  expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize()!.height + 1)
  expect((await demand()).lines).toHaveLength(0)
  await page.screenshot({ path: info.outputPath('bom-preview-invalid.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()

  const stopExpecting = expectHttpError(page, `/api/business/projects/${project.id}/import-preview/`, 400)
  await upload.setInputFiles({ name: 'wrong.csv', mimeType: 'text/csv', buffer: Buffer.from('任务名称,阶段\n设计,T0') })
  await expect(dialog.getByRole('alert')).toContainText('表头')
  await expect(confirm).toBeDisabled()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  stopExpecting()

  await uploadRows([goodRow])
  await expect(dialog.getByRole('status')).toContainText('校验通过，共 1 条明细')
  await expect(confirm).toBeEnabled()
  await expect(confirm).toBeInViewport()
  expect((await demand()).lines).toHaveLength(0)
  await page.screenshot({ path: info.outputPath('bom-preview-valid.png'), animations: 'disabled' })
  await confirm.click()
  const action = page.getByRole('dialog', { name: '确认导入 BOM 与物料', exact: true })
  await expect(action).toBeVisible()
  await expect(dialog).toBeHidden()
  await action.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeVisible()
  await confirm.click()
  await action.getByRole('button', { name: '保存', exact: true }).click()
  await expect(action).toBeHidden()
  await expect(dialog).toBeHidden()
  const saved = (await demand()).lines
  expect(saved).toHaveLength(1)
  expect(saved[0]).toMatchObject({ item_name: name, quantity: '4.000', assembly_unit: '机械手', required_date: '2026-09-25' })
})

test('BOM模板提供可转发的逐列填写说明', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/bom')
  const select = page.getByRole('combobox', { name: '项目筛选', exact: true })
  const choice = select.locator('option').nth(1)
  await expect(choice).toBeAttached()
  await select.selectOption((await choice.getAttribute('value'))!)
  await expect(page.getByText('Excel 模板自带“填写说明”页和表头提示', { exact: false })).toBeVisible()
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载填写说明', exact: true }).click()
  const file = await downloading
  expect(file.suggestedFilename()).toBe('BOM导入填写说明.html')
  const content = await readFile((await file.path())!, 'utf8')
  for (const text of ['BOM导入模板填写说明', '新增物料必填', '物料编码＋单元', '不是任务的执行人账号', '下拉', '标红', '实际材质、尺寸']) expect(content).toContain(text)
  await expect(page.getByText('产品编码类别、标准/非标可下拉选择', { exact: false })).toBeVisible()
  await page.screenshot({ path: info.outputPath('bom-import-guide.png'), animations: 'disabled' })
})

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
    ['items', 'masterdata?section=items', '物料'], ['partners', 'masterdata?section=partners', '往来单位'],
    ['sales', 'sales', '销售'], ['projects', 'projects', '项目'], ['purchases', 'purchases', '采购'],
    ['stocks', 'inventory?section=stocks', '期初库存'], ['moves', 'inventory?section=moves', '项目领料'],
    ['entries', 'finance?section=entries', '项目费用'], ['payments', 'finance?section=payments', '收付款记录'],
    ['tasks', `projects/${projectId}?tab=tasks&section=tasks`, '项目任务'],
    ['time', `projects/${projectId}?tab=tasks&section=time`, '工时'],
    ['deliveries', `projects/${projectId}?tab=deliveries&section=deliveries`, '发货'],
  ]
  const evidence: Record<string, unknown>[] = []
  for (const [resource, route, title] of cases) {
    await page.goto(`/erp/${route}`)
    await openImport(page)
    const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
    await expect(dialog.getByText('① 先准备：', { exact: true })).toBeVisible()
    await expect(dialog.getByText('② 最少填什么：', { exact: true })).toBeVisible()
    await dialog.getByLabel('模板格式').selectOption('csv')
    await dialog.getByText('模板字段与页面列对应说明', { exact: true }).click()
    const fieldLabels = dialog.locator('.import-field-guide .el-table__body tr td:first-child')
    await expect(fieldLabels.first()).toBeVisible()
    const labels = (await fieldLabels.allTextContents()).map(s => s.trim())
    expect(labels.length).toBeGreaterThan(0)
    const guideDownload = page.waitForEvent('download')
    await dialog.getByRole('button', { name: '下载填写说明', exact: true }).click()
    const guide = await guideDownload
    expect(guide.suggestedFilename()).toBe(`${title}导入填写说明.html`)
    const guideContent = await readFile((await guide.path())!, 'utf8')
    expect(guideContent).toContain('示例仅说明格式，请替换为真实业务数据')
    expect(guideContent).toContain('选中数据单元格可看到填写提示')
    expect(guideContent).toContain('第一次填写，照这三步做')
    expect(guideContent).toContain('去哪找 / 怎么选')
    await expect(dialog.getByText('固定取值可下拉选择', { exact: false })).toBeVisible()
    for (const label of labels) expect(guideContent).toContain(label)
    if (resource === 'tasks') await page.screenshot({ path: info.outputPath('task-import-guide.png'), animations: 'disabled' })
    const downloading = page.waitForEvent('download')
    await dialog.getByRole('button', { name: '下载模板', exact: true }).click()
    const file = await downloading
    expect(file.suggestedFilename()).toBe(`${title}导入模板.csv`)
    const content = (await readFile((await file.path())!, 'utf8')).replace(/^\uFEFF/, '').trim()
    expect(content.split(',')).toEqual(labels)
    expect(new Set(labels).size).toBe(labels.length)
    const stopExpected = expectHttpError(page, `/api/business/${resource}/import-file/`, 400)
    await dialog.locator('input[type=file]').setInputFiles({ name: 'wrong-header.csv', mimeType: 'text/csv', buffer: Buffer.from('错误表头\n不可入库的数据') })
    await expect(dialog.getByRole('alert')).toContainText('表头必须依次为')
    await expect(dialog.getByRole('alert')).toContainText('重新下载模板')
    await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
    stopExpected()
    evidence.push({ resource, templateHeaders: labels, invalidHeaderRejected: true })
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog).toBeHidden()
    await openImport(page)
    await expect(dialog.getByRole('alert')).toHaveCount(0)
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  }
  await info.attach('import-surface-inventory', { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' })
})

test('关闭未确认的导入后重新打开，不应继续提交上次文件', async ({ page }) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/masterdata?section=items')
  await openImport(page)
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  const code = `CANCEL${Date.now()}`
  await dialog.locator('input[type=file]').setInputFiles({ name: 'cancel.csv', mimeType: 'text/csv', buffer: Buffer.from(`物料编码,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位,独立建码原因\n${code},取消导入验收,规格,,,21,品牌,标准件,台,`) })
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  await openImport(page)
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
  await openImport(page)
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
