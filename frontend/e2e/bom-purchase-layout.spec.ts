import { test, expect, login, type Page } from './fixtures'

async function api(page: Page, path: string, data?: object, method: 'post' | 'patch' = 'post') {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() }
  const response = data === undefined
    ? await page.request.get(`/api/${path}`, { headers })
    : await page.request[method](`/api/${path}`, { headers, data })
  expect(response.status(), await response.text()).toBeLessThan(300)
  return response.json()
}

test('BOM 同屏采购桌面左右与移动上下布局，键盘纠错后仅保存一张草稿', async ({ page }, info) => {
  const desktop = info.project.name === 'desktop'
  await page.setViewportSize(desktop ? { width: 1487, height: 1058 } : { width: 390, height: 844 })
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const suffix = `${Date.now()}${desktop ? 'D' : 'M'}`
  const me = await api(page, 'auth/me/')
  // Each run creates only its own one partner, one project and six materials.
  // The authenticated business APIs provide fixtures; UI actions create the purchase.
  const partner = await api(page, 'business/partners/', { name: '示例自动化供应商', kind: 'both', payment_term: 'month30' })
  const project = await api(page, 'business/projects/', {
    name: '电机转子自动装配检测线', customer: partner.id, manager: me.id,
    requirements: `隔离 BOM 界面验收 ${suffix}，非企业实际订单。`, due_date: '2026-09-30',
  })
  const samples = [
    { name: '伺服电机', specification: '750W', brand: '台达', product_category: '21', part_type: 'standard', assembly_unit: '输送单元', quantity: '4' },
    { name: '直线导轨', specification: 'HGR20 / 500mm', brand: 'HIWIN', product_category: '21', part_type: 'standard', assembly_unit: '输送单元', quantity: '8' },
    { name: '光电传感器', specification: '对射型 24V', brand: 'OMRON', product_category: '21', part_type: 'standard', assembly_unit: '检测单元', quantity: '6' },
    { name: '安装底板', specification: '6061 铝板', brand: '', product_category: '11', part_type: 'custom', assembly_unit: '检测单元', quantity: '2' },
    { name: '电控箱', specification: '钣金机柜', brand: '', product_category: '12', part_type: 'custom', assembly_unit: '电气单元', quantity: '1' },
    { name: '气缸', specification: '缸径32 / 行程100', brand: 'SMC', product_category: '21', part_type: 'standard', assembly_unit: '夹紧单元', quantity: '2' },
  ]
  const items: { id: number; code: string }[] = []
  for (const [index, sample] of samples.entries()) {
    const { assembly_unit: _unit, quantity: _quantity, ...material } = sample
    const created = await api(page, 'business/items/', {
      ...material, specification: `${sample.specification} · 隔离验收 ${suffix}`, unit: '件',
      ...(sample.part_type === 'custom' ? { drawing_number: `A26-E-05-P-${suffix}-${index}`, drawing_revision: 'A' } : {}),
    })
    items.push(await api(page, `business/items/${created.id}/`))
  }
  const initialDemand = await api(page, `business/projects/${project.id}/demand/`)
  await api(page, `business/projects/${project.id}/revise-bom/`, {
    expected_revision: initialDemand.revision,
    lines: samples.map((sample, index) => ({ item: items[index]!.id, quantity: sample.quantity, assembly_unit: sample.assembly_unit, change_note: '界面验收初版' })),
  })
  // Only this newly created fixture is disabled; existing master data is untouched.
  await api(page, `business/items/${items[2]!.id}/`, { is_active: false }, 'patch')
  const demand = await api(page, `business/projects/${project.id}/demand/`)
  await page.goto('/erp/purchases')
  await page.getByRole('button', { name: '从 BOM 多选下单', exact: true }).click()
  const workspace = page.getByRole('region', { name: 'BOM 勾选采购', exact: true })
  const draft = workspace.getByRole('region', { name: '采购草稿', exact: true })
  const selection = workspace.getByRole('status', { name: 'BOM 选择状态', exact: true })
  const materialPane = workspace.locator('.purchase-materials')
  await workspace.getByLabel('采购项目', { exact: true }).selectOption(String(project.id))
  await expect(selection).toContainText('已选 0 项 · 筛选结果 6 项')
  await expect(workspace.getByRole('checkbox', { name: `选择 ${items[2]!.code}`, exact: true })).toBeDisabled()

  const search = workspace.getByLabel('搜索 BOM 物料', { exact: true })
  await search.fill('伺服电机')
  const first = workspace.getByRole('checkbox', { name: `选择 ${items[0]!.code}`, exact: true })
  await first.focus()
  await first.press('Space')
  await expect(first).toBeChecked()
  await search.fill('')
  for (const index of [1, 5]) {
    const checkbox = workspace.getByRole('checkbox', { name: `选择 ${items[index]!.code}`, exact: true })
    await checkbox.focus()
    await checkbox.press('Space')
    await expect(checkbox).toBeChecked()
  }
  await expect(selection).toContainText('已选 3 项 · 筛选结果 6 项')
  await expect(materialPane.locator('.el-table__body tbody tr')).toHaveCount(6)
  await draft.getByLabel('供应商', { exact: true }).selectOption(String(partner.id))
  await draft.getByLabel('交期', { exact: true }).fill('2026-09-18')
  await expect(draft).toContainText('每批合格收货当月月底 + 30天')
  const quantities = draft.getByLabel('采购数量', { exact: true })
  const prices = draft.getByLabel('含税单价（元）', { exact: true })
  await quantities.first().focus()
  await quantities.first().press('Tab')
  await expect(prices.first()).toBeFocused()
  for (const [index, price] of ['1500', '260', '180'].entries()) await prices.nth(index).fill(price)
  let purchaseRequests = 0
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/api/business/purchases/' && request.method() === 'POST') purchaseRequests++
  })
  await quantities.first().fill('0')
  await quantities.first().press('Enter')
  await expect(workspace.getByRole('alert')).toContainText('采购数量必须大于零')
  expect(purchaseRequests).toBe(0)
  expect((await api(page, `business/purchases/?project=${project.id}`)).count).toBe(0)
  await quantities.first().fill('4')
  await workspace.getByRole('button', { name: '刷新缺料', exact: true }).click()
  await expect(workspace.getByRole('alert')).toHaveCount(0)
  await expect(prices.first()).toHaveValue('1500')
  await expect(draft.getByLabel('含税合计', { exact: true })).toHaveText('¥ 8,440.00')

  await expect(workspace.getByRole('button', { name: /(?:折叠|展开)采购草稿/ })).toHaveCount(0)
  await expect(draft).toBeVisible()

  await materialPane.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate(element => { element.scrollTop = 0 })
  await draft.locator('.draft-items').evaluate(element => { element.scrollTop = 0 })
  if (desktop) await page.evaluate(() => window.scrollTo(0, 0))
  else await workspace.scrollIntoViewIfNeeded()
  const materialsBox = (await materialPane.boundingBox())!
  const draftBox = (await draft.boundingBox())!
  expect(materialsBox.x).toBeGreaterThanOrEqual(0)
  expect(draftBox.x + draftBox.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  if (desktop) {
    expect(draftBox.x).toBeGreaterThanOrEqual(materialsBox.x + materialsBox.width)
    expect(Math.abs(draftBox.y - materialsBox.y)).toBeLessThan(8)
  } else {
    expect(draftBox.y).toBeGreaterThanOrEqual(materialsBox.y + materialsBox.height)
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  if (!desktop) await workspace.getByRole('heading', { name: 'BOM 勾选采购', exact: true }).scrollIntoViewIfNeeded()
  if (desktop) {
    await expect(materialPane.locator('.el-table__body tbody tr').first()).toBeInViewport({ ratio: 0.9 })
    await expect(materialPane.locator('.el-table__body tbody tr').last()).toBeInViewport({ ratio: 0.9 })
    for (const item of await draft.locator('.draft-item').all()) await expect(item).toBeInViewport({ ratio: 0.9 })
    await expect(draft.getByRole('button', { name: '保存采购草稿', exact: true })).toBeInViewport({ ratio: 1 })
    const saveButton = (await draft.getByRole('button', { name: '保存采购草稿', exact: true }).boundingBox())!
    expect(saveButton.y + saveButton.height).toBeLessThanOrEqual(page.viewportSize()!.height)
  }
  await page.screenshot({ path: info.outputPath(`bom-purchase-layout-${info.project.name}.png`), animations: 'disabled' })
  if (!desktop) {
    await draft.scrollIntoViewIfNeeded()
    await page.screenshot({ path: info.outputPath('bom-purchase-layout-mobile-draft.png'), animations: 'disabled' })
  }
  const saved = page.waitForResponse(response => new URL(response.url()).pathname === '/api/business/purchases/' && response.request().method() === 'POST')
  await prices.last().press('Enter')
  const response = await saved
  expect(response.status(), await response.text()).toBe(201)
  await expect(workspace).not.toBeVisible()
  expect(purchaseRequests).toBe(1)
  const purchases = await api(page, `business/purchases/?project=${project.id}`)
  expect(purchases.count).toBe(1)
  const purchase = purchases.results[0]
  expect(purchase).toMatchObject({ status: 'draft', supplier: partner.id, payment_term: 'month30', payment_days: 30, due_date: '2026-09-18' })
  expect(purchase.lines).toHaveLength(3)
  for (const [offset, index] of [0, 1, 5].entries()) {
    const bom = demand.lines.find((line: { item: number }) => line.item === items[index]!.id)
    expect(purchase.lines.find((line: { item: number }) => line.item === items[index]!.id)).toMatchObject({
      bom_line: bom.bom_line, quantity: `${samples[index]!.quantity}.000`, unit_price: ['1500.00', '260.00', '180.00'][offset],
    })
  }
  await page.goto(`/erp/projects/${project.id}?tab=bom`)
  const projectBom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await projectBom.getByRole('checkbox', { name: `选择 ${items[3]!.code} ${samples[3]!.assembly_unit}`, exact: true }).check()
  await projectBom.getByRole('button', { name: '按缺料采购', exact: true }).click()
  await expect(draft.locator('.draft-item')).toHaveCount(1)
  await expect(draft.locator('.draft-item')).toContainText('安装底板')
  await expect(draft.getByLabel('采购数量', { exact: true })).toHaveValue('2.000')
  await workspace.getByRole('button', { name: '返回列表', exact: true }).click()
  await expect(projectBom.getByRole('button', { name: '按缺料采购', exact: true })).toBeFocused()
  expect(purchaseRequests).toBe(1)
  await info.attach('bom-layout-fixture', { body: JSON.stringify({ project: project.id, purchase: purchase.id, itemCodes: items.map(item => item.code) }), contentType: 'application/json' })
})
