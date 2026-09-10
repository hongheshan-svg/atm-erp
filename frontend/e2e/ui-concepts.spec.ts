import { test, expect, login } from './fixtures'

test('概念图全部页面与子模块在真实数据下可查看，侧边详情可关闭', async ({ page }, info) => {
  test.setTimeout(240000)
  if (info.project.name === 'desktop') await page.setViewportSize({ width: 1487, height: 1058 })
  await page.goto('/erp/login')
  await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
  await page.screenshot({ path: info.outputPath('01-login.png'), animations: 'disabled' })
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const day = new Date().toISOString().slice(0, 10)
  async function post(path: string, data: object) {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.ok(), await response.text()).toBeTruthy()
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const partner = await post('partners/', { name: '星海自动化 · 界面验收', kind: 'both', address: '自动化产业园 8 号', phone: '010-12345678' })
  const item = await post('items/', { name: '伺服电机 · 界面验收', specification: '750W · 带制动器', brand: '三菱', unit: '台', part_type: 'standard', duplicate_reason: '隔离界面验收样本' })
  await post('stocks/opening/', { item: item.id, quantity: '6', unit_cost: '100', location: '主仓-A02', reason: '隔离界面验收期初样本' })
  const sale = await post('sales/', { name: '转子自动装配检测线 · 界面验收', customer: partner.id, manager: me.id, requirements: '工件转子；自动上料、装配、视觉检测；验收指标按技术协议确认。', equipment_quantity: 2, warranty_months: 12, due_date: '2026-12-30' })
  await post(`sales/${sale.id}/quote/`, { amount: '680000', reason: '隔离界面验收报价' })
  const signed = await post(`sales/${sale.id}/sign/`, { date: day, manager: me.id, milestones: [{ title: '合同预付款', amount: '204000', due_date: day }, { title: '验收款', amount: '476000', due_date: '2026-12-30' }] })
  const project = signed.project
  const demand = await (await page.request.get(`/api/business/projects/${project}/demand/`, { headers })).json()
  await post(`projects/${project}/revise-bom/`, { expected_revision: demand.revision, lines: [{ item: item.id, quantity: '10', assembly_unit: '上料单元', change_note: '隔离验收初版' }] })
  const task = await post('tasks/', { project, title: '机械方案设计', kind: 'design', assignee: me.id, due_date: '2026-12-01' })
  const purchase = await post('purchases/', { project, supplier: partner.id, due_date: '2026-12-10', payment_term: 'month30', lines: [{ item: item.id, quantity: '4', unit_price: '100' }] })
  await post(`purchases/${purchase.id}/submit/`, {})
  await post(`purchases/${purchase.id}/approve/`, { reason: '隔离界面验收管理员批准例外' })
  const upload = await page.request.post('/api/business/documents/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, multipart: { sale: String(sale.id), category: 'contract', file: { name: '技术协议-界面验收.txt', mimeType: 'text/plain', buffer: Buffer.from('隔离 UI 验收附件，不是企业实际合同。') } } })
  expect(upload.ok()).toBeTruthy()
  const routes = [
    ['02-workbench', '/workbench', '工作台'], ['03-reports', '/reports', '经营报表'],
    ['04-sales', '/sales', '销售'], ['05-projects', '/projects', '项目'],
    ['06-project-tasks', `/projects/${project}?tab=tasks&section=tasks`, '转子自动装配检测线 · 界面验收'],
    ['07-bom', `/bom?project=${project}`, 'BOM'], ['08-purchases', '/purchases', '采购'],
    ['09-contract', `/purchases/${purchase.id}/contract`, '采购合同预览'],
    ['10-inventory', '/inventory?section=stocks', '库存'], ['11-finance', `/finance?section=entries&project=${project}`, '收付款'],
    ['12-materials', '/masterdata?section=items', '基础资料'], ['13-settings', '/settings?section=users', '设置'],
    ['14-setup-ready', '/setup', '配置已就绪'],
    ['inventory-moves', `/inventory?section=moves&project=${project}`, '库存'],
    ['masterdata-partners', '/masterdata?section=partners', '基础资料'],
    ...['reconciliations', 'monthly', 'payments', 'bank'].map(section => [`finance-${section}`, `/finance?section=${section}&project=${project}`, '收付款']),
    ...['company', 'codes', 'audit', 'account'].map(section => [`settings-${section}`, `/settings?section=${section}`, '设置']),
    ...[['tasks', 'time'], ['bom', 'demand'], ['bom', 'lines'], ['deliveries', 'deliveries'], ['deliveries', 'service'], ['finance', 'entries'], ['finance', 'reconciliations'], ['finance', 'payments'], ['cost', 'budget'], ['cost', 'actual']].map(([tab, section]) => [`project-${tab}-${section}`, `/projects/${project}?tab=${tab}&section=${section}`, '转子自动装配检测线 · 界面验收']),
    ['project-purchases', `/projects/${project}?tab=purchases`, '转子自动装配检测线 · 界面验收'],
    ['project-documents', `/projects/${project}?tab=documents`, '转子自动装配检测线 · 界面验收'],
  ]
  for (const [name, path, heading] of routes) {
    await page.goto('/erp' + path)
    await expect(page.getByRole('heading', { name: heading, exact: true }).first()).toBeVisible()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.el-skeleton:visible')).toHaveCount(0)
    await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
    await expect(page.locator('[role="alert"]:visible.el-alert--error')).toHaveCount(0)
    await page.screenshot({ path: info.outputPath(name + '.png'), animations: 'disabled' })
    const width = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }))
    expect(width.document, `${name} 不应出现整页横向溢出`).toBeLessThanOrEqual(width.viewport + 1)
  }
  await page.goto('/erp/sales')
  const saleDetail = await (await page.request.get(`/api/business/sales/${sale.id}/`, { headers })).json()
  await page.getByRole('button', { name: saleDetail.code, exact: true }).click()
  const detail = page.getByRole('dialog', { name: '销售明细', exact: true })
  await expect(detail).toBeVisible()
  await expect(detail.getByRole('button', { name: '下载 技术协议-界面验收.txt', exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('sales-details.png'), animations: 'disabled' })
  await detail.getByRole('button', { name: '关闭详情', exact: true }).click()
  await expect(detail).toHaveCount(0)
  for (const [name, path] of [
    ['purchase-details', `/purchases?resource=purchases&focus=${purchase.id}`],
    ['task-details', `/projects/${project}?tab=tasks&resource=tasks&focus=${task.id}`],
  ]) {
    await page.goto('/erp' + path)
    const pane = page.getByRole('dialog')
    await expect(pane).toBeVisible()
    await page.waitForLoadState('networkidle')
    await expect(pane.getByRole('button', { name: '关闭', exact: true })).toBeInViewport()
    await page.screenshot({ path: info.outputPath(name + '.png'), animations: 'disabled' })
    await pane.getByRole('button', { name: '关闭', exact: true }).click()
  }
  await page.goto('/erp/masterdata?section=items')
  await page.getByRole('button', { name: '新增物料', exact: true }).click()
  await page.getByRole('dialog').getByLabel('物料名称', { exact: true }).fill('定位治具底板')
  await page.screenshot({ path: info.outputPath('material-form.png'), animations: 'disabled' })
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()
  await page.goto('/erp/settings?section=users')
  await page.getByRole('button', { name: '新增用户', exact: true }).click()
  await page.screenshot({ path: info.outputPath('user-form.png'), animations: 'disabled' })
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()
  await page.goto('/erp/settings?section=audit')
  await page.getByRole('region', { name: '操作审计', exact: true }).locator('.record-link').first().click()
  await expect(page.getByRole('dialog', { name: '操作审计详情', exact: true })).toBeVisible()
  await expect(page.getByRole('dialog').getByLabel('详情', { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('audit-details.png'), animations: 'disabled' })
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  if (info.project.name === 'desktop') {
    for (const width of [768, 1024]) {
      await page.setViewportSize({ width, height: 1024 })
      for (const [name, path] of [
        ['workbench', '/workbench'], ['reports', '/reports'], ['bom', `/bom?project=${project}`],
        ['contract', `/purchases/${purchase.id}/contract`], ['inventory', '/inventory?section=stocks'], ['settings', '/settings?section=users'],
      ]) {
        await page.goto('/erp' + path)
        await page.waitForLoadState('networkidle')
        await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
        expect(await page.evaluate(() => document.documentElement.scrollWidth), `${name} 在 ${width}px 不应整页溢出`).toBeLessThanOrEqual(width + 1)
        await page.screenshot({ path: info.outputPath(`tablet-${width}-${name}.png`), animations: 'disabled' })
      }
    }
  }
})
