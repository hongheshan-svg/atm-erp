import { test, expect, login, openRowAction } from './fixtures'

test('已整理的收款冲销后重新出现在待收列表并保留删除和恢复记录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = `${Date.now()}-${info.project.name}`
  const title = `冲销恢复${suffix}`
  const today = new Date().toISOString().slice(0, 10)
  const get = async (path: string) => {
    const response = await page.request.get(`/api/${path}`, { headers })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const post = async (path: string, data: object) => {
    const response = await page.request.post(`/api/business/${path}`, {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data,
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await get('auth/me/')
  const customer = await post('partners/', { name: title, kind: 'customer' })
  const sale = await post('sales/', { name: title, customer: customer.id, manager: me.id })
  await post(`sales/${sale.id}/quote/`, { amount: '100', reason: '隔离验收' })
  const signed = await post(`sales/${sale.id}/sign/`, {
    date: today, manager: me.id, milestones: [{ title, amount: '100', due_date: today }],
  })
  const entry = (await get(`business/entries/?project=${signed.project}`)).results[0]
  const payment = await post(`entries/${entry.id}/pay/`, { amount: '100', date: today, method: 'cash', reason: '原始收款' })
  await post('record-deletions/', { resource: 'payments', ids: [payment.id], reason: '已结清流水整理' })
  await post('record-deletions/', { resource: 'entries', ids: [entry.id], reason: '已结清款项整理' })
  await page.goto(`/erp/projects/${signed.project}?tab=finance&section=entries`)
  const rows = page.locator('.el-table__body tr:visible').filter({ hasText: title })
  await expect(rows).toHaveCount(0)
  await post(`payments/${payment.id}/reverse/`, { date: today, reason: '核对发现收款误录' })
  await page.reload()
  await expect(rows).toHaveCount(1)
  await expect(rows).toContainText('100.00')
  await openRowAction(page, rows, '查看收付流水')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('原始收款')
  await expect(dialog).toContainText('核对发现收款误录')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '已删除记录', exact: true }).click()
  await expect(dialog).toContainText('已结清款项整理')
  await expect(dialog).toContainText('已恢复')
  await page.screenshot({ path: info.outputPath('reopened-entry-history.png'), animations: 'disabled' })
  const payments = (await get(`business/payments/?entry=${entry.id}`)).results
  expect(payments).toHaveLength(2)
  expect(payments.reduce((sum: number, row: { amount: string }) => sum + Number(row.amount), 0)).toBe(0)
})

test('管理员批量删除后可核对记录，普通岗位没有删除入口', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = `${Date.now()}-${info.project.name}`
  const name = `删除验收${suffix}`
  const ids: number[] = []
  for (const index of [1, 2]) {
    const response = await page.request.post('/api/business/partners/', {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { name: `${name}-${index}`, kind: 'customer' },
    })
    expect(response.status(), await response.text()).toBe(201)
    ids.push((await response.json()).id)
  }
  await page.goto('/erp/masterdata?section=partners')
  await page.locator('input[type="search"]').fill(name)
  await page.locator('form.resource-search').evaluate((element: HTMLFormElement) => element.requestSubmit())
  const rows = page.locator('.el-table__body tr:visible').filter({ hasText: name })
  await expect(rows).toHaveCount(2)
  for (const row of await rows.all()) await row.getByRole('checkbox').check()
  await page.getByRole('button', { name: '批量删除（2）', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText(`${name}-1`)
  await expect(dialog.getByRole('button', { name: '确认删除 2 条', exact: true })).toBeDisabled()
  await dialog.getByLabel('删除原因', { exact: true }).fill('隔离环境验收：清理误建资料')
  await dialog.getByRole('checkbox').check()
  await page.screenshot({ path: info.outputPath('delete-confirm.png'), animations: 'disabled' })
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/record-deletions/'))
  await dialog.getByRole('button', { name: '确认删除 2 条', exact: true }).click()
  expect((await pending).status()).toBe(200)
  await expect(dialog).toBeHidden()
  await expect(rows).toHaveCount(0)
  await page.getByRole('button', { name: '已删除记录', exact: true }).click()
  await expect(dialog).toContainText(`${name}-1`)
  await expect(dialog).toContainText('隔离环境验收：清理误建资料')
  await dialog.getByRole('button', { name: '查看删除时内容', exact: true }).first().click()
  await expect(dialog.locator('dl')).toContainText(name)
  await page.screenshot({ path: info.outputPath('deleted-history.png'), animations: 'disabled' })
  const history = await page.request.get('/api/business/record-deletions/?resource=partners', { headers })
  expect(history.status()).toBe(200)
  expect((await history.json()).results.filter((record: { detail: { record: { id: number } } }) => ids.includes(record.detail.record.id))).toHaveLength(2)

  const username = `deletion_finance_${suffix}`, password = 'Deletion-Test-Only-2026'
  const created = await page.request.post('/api/auth/users/', {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { username, password, display_name: '删除权限验收', role: 'finance' },
  })
  expect(created.status(), await created.text()).toBe(201)
  await page.evaluate(() => localStorage.clear())
  await login(page, username, password)
  await page.goto('/erp/finance?section=entries')
  await expect(page.locator('h1')).toContainText('收付款')
  await expect(page.getByRole('button', { name: /批量删除|已删除记录/ })).toHaveCount(0)
  const financeToken = await page.evaluate(() => localStorage.getItem('access_token'))
  const denied = await page.request.post('/api/business/record-deletions/', {
    headers: { Authorization: `Bearer ${financeToken}`, 'Idempotency-Key': crypto.randomUUID() },
    data: { resource: 'partners', ids, reason: '越权应拒绝' },
  })
  expect(denied.status()).toBe(403)
})

test('BOM独立列表及销售附件支持删除和已删除记录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const suffix = `${Date.now()}-${info.project.name}`
  const get = async (path: string) => {
    const response = await page.request.get(`/api/${path}`, { headers })
    expect(response.status(), await response.text()).toBe(200)
    return response.json()
  }
  const post = async (path: string, data: object) => {
    const response = await page.request.post(`/api/business/${path}`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await get('auth/me/')
  const partner = await post('partners/', { name: `删除独立列表${suffix}`, kind: 'customer' })
  const project = await post('projects/', { name: `BOM删除${suffix}`, customer: partner.id, manager: me.id })
  const item = await post('items/', { code: `DEL-${suffix}`, name: `删除物料${suffix}`, specification: '测试', unit: '件' })
  const demand = await get(`business/projects/${project.id}/demand/`)
  await post(`projects/${project.id}/revise-bom/`, { expected_revision: demand.revision, lines: [
    { item: item.id, assembly_unit: 'A单元', quantity: '2', change_note: '首次录入' },
    { item: item.id, assembly_unit: 'B单元', quantity: '3', change_note: '首次录入' },
  ] })
  await page.goto(`/erp/projects/${project.id}?tab=bom`)
  const bom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await expect(bom).toBeVisible()
  const rows = bom.locator('.el-table__body tr:visible')
  await expect(rows).toHaveCount(2)
  for (const row of await rows.all()) await row.getByRole('checkbox').check()
  await bom.getByRole('button', { name: '批量删除（2）', exact: true }).click()
  let dialog = page.getByRole('dialog', { name: '确认删除 2 条BOM明细', exact: true })
  await dialog.getByLabel('删除原因').fill('误建两条用料')
  await dialog.getByRole('checkbox').check()
  await dialog.getByRole('button', { name: '确认删除 2 条', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(bom).toContainText('尚未维护 BOM')
  expect((await get(`business/projects/${project.id}/demand/`)).lines).toHaveLength(0)
  await bom.getByRole('button', { name: '已删除记录', exact: true }).click()
  dialog = page.getByRole('dialog', { name: 'BOM明细 · 已删除记录', exact: true })
  await expect(dialog.locator('article')).toHaveCount(2)
  await page.screenshot({ path: info.outputPath('bom-deleted-history.png'), animations: 'disabled' })
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()

  const sale = await post('sales/', { name: `附件删除${suffix}`, customer: partner.id, manager: me.id })
  const uploaded = await page.request.post('/api/business/documents/', {
    headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, multipart: {
      sale: String(sale.id), category: 'other', file: { name: `误传${suffix}.txt`, mimeType: 'text/plain', buffer: Buffer.from('隔离测试资料') },
    },
  })
  expect(uploaded.status(), await uploaded.text()).toBe(201)
  await page.goto('/erp/sales')
  await page.locator('input[type="search"]').fill(`附件删除${suffix}`)
  await page.locator('form.resource-search').evaluate((element: HTMLFormElement) => element.requestSubmit())
  const saleRow = page.locator('.el-table__body tr:visible').filter({ hasText: `附件删除${suffix}` })
  await saleRow.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name: '附件', exact: true }).click()
  const attachments = page.getByRole('dialog').filter({ has: page.getByRole('button', { name: '上传附件', exact: true }) })
  await expect(attachments).toContainText(`误传${suffix}.txt`)
  await attachments.getByRole('button', { name: '删除', exact: true }).click()
  dialog = page.getByRole('dialog', { name: '确认删除 1 条附件', exact: true })
  await dialog.getByLabel('删除原因').fill('附件误传验收')
  await dialog.getByRole('checkbox').check()
  await dialog.getByRole('button', { name: '确认删除 1 条', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(attachments).not.toContainText(`误传${suffix}.txt`)
  await attachments.getByRole('button', { name: '已删除记录', exact: true }).click()
  dialog = page.getByRole('dialog', { name: '附件 · 已删除记录', exact: true })
  await expect(dialog.locator('article')).toHaveCount(1)
  await expect(dialog).toContainText('附件误传验收')
  await page.screenshot({ path: info.outputPath('attachment-deleted-history.png'), animations: 'disabled' })
})

test('BOM按筛选跨页全选427项并一次删除，保留筛选外明细', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const suffix = Date.now() + '-' + info.project.name
  const post = async (path: string, data: object) => {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const customer = await post('partners/', { name: '跨页BOM客户' + suffix, kind: 'customer' })
  const project = await post('projects/', { name: '跨页BOM验收' + suffix, customer: customer.id, manager: me.id })
  const item = await post('items/', { code: 'STD-' + suffix, name: '跨页删除标准物料', specification: '验收' + suffix, unit: '件', part_type: 'standard' })
  const other = await post('items/', { code: 'CUSTOM-' + suffix, name: '应保留的非标物料', specification: '验收' + suffix, unit: '件', part_type: 'custom' })
  const demandUrl = '/api/business/projects/' + project.id + '/demand/'
  const before = await (await page.request.get(demandUrl, { headers })).json()
  await post('projects/' + project.id + '/revise-bom/', { expected_revision: before.revision, lines: [
    ...Array.from({ length: 427 }, (_, i) => ({ item: item.id, assembly_unit: '单元' + (i + 1), quantity: '1', change_note: '隔离批量删除验收' })),
    { item: other.id, assembly_unit: '保留单元', quantity: '1', change_note: '筛选外应保留' },
  ] })
  await page.goto('/erp/projects/' + project.id + '?tab=bom')
  const bom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await bom.getByLabel('每页显示条目').selectOption('10')
  await bom.getByRole('checkbox', { name: '选择本页BOM明细', exact: true }).check()
  await expect(bom.getByLabel('BOM批量选择')).toContainText('已选 10 项')
  await bom.locator('.el-pager').getByText('2', { exact: true }).click()
  await bom.getByRole('checkbox', { name: '选择本页BOM明细', exact: true }).check()
  await expect(bom.getByLabel('BOM批量选择')).toContainText('已选 20 项')
  await bom.getByLabel('筛选类别').selectOption('standard')
  await expect(bom.getByLabel('BOM批量选择')).toContainText('已选 0 项')
  await bom.getByRole('button', { name: '全选筛选结果（427项，跨页）', exact: true }).click()
  await expect(bom.getByRole('button', { name: '批量删除（427）', exact: true })).toBeEnabled()
  await page.screenshot({ path: info.outputPath('bom-select-427.png'), animations: 'disabled' })
  await bom.getByRole('button', { name: '批量删除（427）', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '确认删除 427 条BOM明细', exact: true })
  await expect(dialog.locator('.deletion-records li')).toHaveCount(427)
  await expect(dialog).not.toContainText('应保留的非标物料')
  await dialog.getByLabel('删除原因').fill('隔离验收：批量清理所选427条BOM')
  await dialog.getByRole('checkbox').check()
  await page.screenshot({ path: info.outputPath('bom-confirm-427.png'), animations: 'disabled' })
  const started = Date.now()
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/record-deletions/'))
  await dialog.getByRole('button', { name: '确认删除 427 条', exact: true }).click()
  expect((await pending).status()).toBe(200)
  await info.attach('批量删除耗时', { body: Buffer.from((Date.now() - started) + ' ms'), contentType: 'text/plain' })
  await expect(dialog).toBeHidden()
  const after = await (await page.request.get(demandUrl, { headers })).json()
  expect(after.lines).toHaveLength(1)
  expect(after.lines[0].item_name).toBe('应保留的非标物料')
  const history = await (await page.request.get('/api/business/record-deletions/?resource=bom&project=' + project.id, { headers })).json()
  expect(history.count).toBe(427)
})

test('基础物料跨页勾选与全选筛选结果后批量删除，保留未选物料', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const suffix = Date.now() + '-' + info.project.name
  const name = '跨页物料' + suffix
  const create = async (index: number, title: string) => {
    const response = await page.request.post('/api/business/items/', {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
      data: { code: 'BATCH-' + suffix + '-' + index, name: title, specification: '隔离验收', unit: '件' },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  for (let i = 1; i <= 21; i++) await create(i, name + '-' + i)
  const kept = await create(22, '筛选外保留' + suffix)
  await page.goto('/erp/masterdata?section=items')
  await page.locator('input[type="search"]').fill(name)
  await page.locator('form.resource-search').evaluate((element: HTMLFormElement) => element.requestSubmit())
  await page.getByLabel('每页显示条目').selectOption('10')
  await page.getByRole('checkbox', { name: '选择本页物料', exact: true }).check()
  await expect(page.getByLabel('物料批量选择')).toContainText('已选 10 项')
  await page.locator('.el-pager').getByText('2', { exact: true }).click()
  await expect(page.getByRole('checkbox', { name: '选择本页物料', exact: true })).not.toBeChecked()
  await page.getByRole('checkbox', { name: '选择本页物料', exact: true }).check()
  await expect(page.getByLabel('物料批量选择')).toContainText('已选 20 项')
  await page.getByRole('button', { name: '全选筛选结果（21项，跨页）', exact: true }).click()
  await page.getByRole('button', { name: '批量删除（21）', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '确认删除 21 条物料', exact: true })
  await expect(dialog.locator('.deletion-records li')).toHaveCount(21)
  await dialog.getByLabel('删除原因').fill('隔离验收：跨页删除21项未使用物料')
  await dialog.getByRole('checkbox').check()
  await page.screenshot({ path: info.outputPath('items-confirm-21.png'), animations: 'disabled' })
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/record-deletions/'))
  await dialog.getByRole('button', { name: '确认删除 21 条', exact: true }).click()
  expect((await pending).status()).toBe(200)
  await expect(dialog).toBeHidden()
  await expect(page.getByLabel('物料批量选择')).toContainText('已选 0 项')
  const remaining = await page.request.get('/api/business/items/?search=' + encodeURIComponent(name), { headers })
  expect((await remaining.json()).count).toBe(0)
  expect((await page.request.get('/api/business/items/' + kept.id + '/', { headers })).status()).toBe(200)
})

test('采购订单可跨页全选21张草稿并整批删除', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const suffix = Date.now() + '-' + info.project.name
  const post = async (path: string, data: object) => {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const partner = await post('partners/', { name: '批量采购验收' + suffix, kind: 'both' })
  const project = await post('projects/', { name: '跨页采购' + suffix, customer: partner.id, manager: me.id })
  const item = await post('items/', { name: '跨页采购用料' + suffix, unit: '件' })
  for (let i = 0; i < 21; i++) await post('purchases/', { project: project.id, supplier: partner.id, due_date: '2026-12-31', lines: [{ item: item.id, quantity: '1', unit_price: '10' }] })
  await page.goto('/erp/projects/' + project.id + '?tab=purchases')
  const allPage = page.getByRole('checkbox', { name: /^选择本页/ })
  await page.getByLabel('每页显示条目').selectOption('10')
  await allPage.check()
  await expect(page.getByRole('button', { name: '批量删除（10）', exact: true })).toBeEnabled()
  await page.locator('.el-pager').getByText('2', { exact: true }).click()
  await expect(allPage).not.toBeChecked()
  await allPage.check()
  await expect(page.getByRole('button', { name: '批量删除（20）', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '全选筛选结果（21项，跨页）', exact: true }).click()
  await page.getByRole('button', { name: '批量删除（21）', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: /^确认删除 21 条/ })
  await expect(dialog.locator('.deletion-records li')).toHaveCount(21)
  await dialog.getByLabel('删除原因').fill('隔离验收：清理21张误建采购草稿')
  await dialog.getByRole('checkbox').check()
  await page.screenshot({ path: info.outputPath('purchase-delete-21.png'), animations: 'disabled' })
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/record-deletions/'))
  await dialog.getByRole('button', { name: '确认删除 21 条', exact: true }).click()
  expect((await pending).status()).toBe(200)
  await expect(dialog).toBeHidden()
  const remaining = await page.request.get('/api/business/purchases/?project=' + project.id, { headers })
  expect((await remaining.json()).count).toBe(0)
})

test('销售附件弹窗跨页全选21个文件，仅删除当前单据的附件', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const suffix = Date.now() + '-' + info.project.name
  const post = async (path: string, data: object) => {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const customer = await post('partners/', { name: '附件客户' + suffix, kind: 'customer' })
  const sale = await post('sales/', { name: '跨页附件验收' + suffix, customer: customer.id, manager: me.id })
  const other = await post('sales/', { name: '附件范围外' + suffix, customer: customer.id, manager: me.id })
  for (let i = 0; i < 22; i++) {
    const response = await page.request.post('/api/business/documents/', {
      headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
      multipart: { sale: String(i < 21 ? sale.id : other.id), category: 'other',
        file: { name: '隔离测试文件' + i + '.txt', mimeType: 'text/plain', buffer: Buffer.from('只用于附件跨页删除验收') } },
    })
    expect(response.status(), await response.text()).toBe(201)
  }
  await page.goto('/erp/sales')
  await page.locator('input[type="search"]').fill('跨页附件验收' + suffix)
  await page.locator('form.resource-search').evaluate((element: HTMLFormElement) => element.requestSubmit())
  const row = page.locator('.el-table__body tr:visible').filter({ hasText: '跨页附件验收' + suffix })
  await openRowAction(page, row, '附件')
  const attachments = page.getByRole('dialog', { name: /^销售附件 · / })
  await attachments.getByLabel('每页显示条目').selectOption('10')
  const allPage = attachments.getByRole('checkbox', { name: '选择本页附件', exact: true })
  await allPage.check()
  await attachments.locator('.el-pager').getByText('2', { exact: true }).click()
  await expect(allPage).not.toBeChecked()
  await allPage.check()
  await expect(attachments.getByLabel('附件批量选择')).toContainText('已选 20 项')
  await attachments.getByRole('button', { name: '全选筛选结果（21项，跨页）', exact: true }).click()
  await attachments.getByRole('button', { name: '批量删除（21）', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '确认删除 21 条附件', exact: true })
  await expect(dialog.locator('.deletion-records li')).toHaveCount(21)
  await dialog.getByLabel('删除原因').fill('隔离验收：批量清理当前销售单误传文件')
  await dialog.getByRole('checkbox').check()
  await page.screenshot({ path: info.outputPath('attachment-delete-21.png'), animations: 'disabled' })
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/record-deletions/'))
  await dialog.getByRole('button', { name: '确认删除 21 条', exact: true }).click()
  expect((await pending).status()).toBe(200)
  await expect(dialog).toBeHidden()
  await expect(attachments.getByLabel('附件批量选择')).toContainText('已选 0 项')
  expect((await (await page.request.get('/api/business/documents/?sale=' + sale.id, { headers })).json()).count).toBe(0)
  expect((await (await page.request.get('/api/business/documents/?sale=' + other.id, { headers })).json()).count).toBe(1)
})
