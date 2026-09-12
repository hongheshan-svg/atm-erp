import { test, expect, login, type Page } from './fixtures'

async function read(page: Page, path: string) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const response = await page.request.get('/api/business/' + path, { headers: { Authorization: `Bearer ${token}` } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}
async function importRows(page: Page, title: string, content: string) {
  await expect(page.getByRole('region', { name: title, exact: true })).toBeVisible()
  await page.getByRole('button', { name: '导入', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  await dialog.locator('input[type=file]').setInputFiles({ name: 'rows.csv', mimeType: 'text/csv', buffer: Buffer.from(content) })
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  const pending = page.waitForResponse(r => r.url().endsWith('/import-confirm/') && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(200)
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  return response.json()
}

test('BOM 同屏采购跨页筛选保留草稿编辑，按准确含税金额保存所选明细', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const tag = `BOM${Date.now()}`
  await page.goto('/erp/masterdata?section=partners')
  const partner = await importRows(page, '客户与供应商', `名称,类型,联系人,电话,地址\n${tag},both,,,\n`)
  const partnerRow = await read(page, `partners/${partner.results[0].id}/`)
  await page.getByRole('tab', { name: '物料', exact: true }).click()
  const items = await importRows(page, '物料', '物料编码,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位,独立建码原因\n' + Array.from({ length: 13 }, (_, i) => `${tag}-${i},测试件${tag}-${i},规格,${i < 12 ? '' : `A26-E-05-P-${tag.slice(-6)}`},${i < 12 ? '' : 'A'},${i < 12 ? '21' : '11'},${i < 12 ? '品牌A' : '品牌B'},${i < 12 ? 'standard' : 'custom'},件,`).join('\n'))
  await page.goto('/erp/projects')
  const project = await importRows(page, '项目列表', `名称,客户编码,负责人账号,需求说明,计划交期,设备数量,质保月数,成员账号（分号分隔）\n${tag},${partnerRow.code},admin,,,1,12,\n`)
  const projectId = project.results[0].id
  await page.goto(`/erp/projects/${projectId}`)
  await page.getByRole('tab', { name: 'BOM', exact: true }).click()
  const bom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await bom.locator('input[type=file]').setInputFiles({ name: 'bom.csv', mimeType: 'text/csv', buffer: Buffer.from('物料编码,单元,需求数量,变更说明,需求日期,申请日期,申请人\n' + Array.from({ length: 13 }, (_, i) => `${tag}-${i},${i < 12 ? '上料单元' : '检测单元'},1,初版,2026-10-01,2026-09-11,设计员`).join('\n')) })
  await expect(bom.locator('.import-preview thead')).toContainText('物料编码')
  await expect(bom.locator('.import-preview thead')).toContainText('单元')
  await expect(bom.locator('.import-preview tbody tr').first()).toContainText(`${tag}-0`)
  await expect(bom.locator('.import-preview tbody tr').first()).toContainText('上料单元')
  await bom.getByRole('button', { name: '确认导入', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  const demand = await read(page, `projects/${projectId}/demand/`)
  expect(demand.lines[0].required_date).toBe('2026-10-01')
  expect(demand.lines[0].applicant).toBe('设计员')
  await page.goto('/erp/purchases')
  await page.getByRole('button', { name: '从 BOM 多选下单', exact: true }).click()
  const picker = page.getByRole('region', { name: 'BOM 勾选采购', exact: true })
  const order = picker.getByRole('region', { name: '采购草稿', exact: true })
  await expect(picker).toBeVisible()
  await expect(order).toBeVisible()
  await expect(order.getByRole('button', { name: '保存采购草稿', exact: true })).toBeDisabled()
  await picker.getByLabel('采购项目').selectOption(String(projectId))
  async function filter(label: string, value: string) {
    const input = picker.getByRole('combobox', { name: label, exact: true })
    await expect(input).toBeEnabled()
    await input.focus()
    await input.press('ArrowDown')
    await page.getByRole('option', { name: value, exact: true }).click()
    await page.keyboard.press('Escape')
  }
  await filter('筛选品牌', '品牌A')
  await filter('筛选单元', '上料单元')
  await filter('筛选类别', '标准件')
  await filter('筛选产品编码类别', '无图·标准件')
  await expect(picker.getByRole('status', { name: 'BOM 选择状态', exact: true })).toContainText('筛选结果 12 项')
  await picker.getByRole('checkbox', { name: `选择 ${tag}-0`, exact: true }).check()
  await order.getByLabel('供应商', { exact: true }).selectOption(String(partnerRow.id))
  await order.getByLabel('交期', { exact: true }).fill('2026-09-30')
  await order.getByLabel('结算方式', { exact: true }).selectOption('month30')
  await expect(order).toContainText(/收货.*当月月底/)
  await expect(order).toContainText(/30\s*天/)
  await expect(order.getByLabel('采购数量', { exact: true })).toHaveCount(1)
  await order.getByLabel('采购数量', { exact: true }).fill('0.333')
  await order.getByLabel('含税单价（元）', { exact: true }).fill('10.01')
  await picker.locator('.list-pagination').getByRole('button', { name: '下一页', exact: true }).click()
  await picker.getByRole('checkbox', { name: `选择 ${tag}-10`, exact: true }).check()
  await order.getByLabel('含税单价（元）', { exact: true }).nth(1).fill('20.02')
  await filter('筛选品牌', '品牌B')
  await filter('筛选单元', '检测单元')
  await filter('筛选类别', '非标件')
  await filter('筛选产品编码类别', '有图·机加')
  await expect(picker.getByRole('status', { name: 'BOM 选择状态', exact: true })).toContainText('已选 2 项 · 筛选结果 13 项')
  await picker.locator('.list-pagination').getByRole('button', { name: '下一页', exact: true }).click()
  await picker.getByRole('checkbox', { name: `选择 ${tag}-12`, exact: true }).check()
  await order.getByLabel('含税单价（元）', { exact: true }).nth(2).fill('30.03')
  await expect(picker.getByRole('status', { name: 'BOM 选择状态', exact: true })).toContainText('已选 3 项 · 筛选结果 13 项')
  await expect(order.getByLabel('采购数量', { exact: true })).toHaveCount(3)
  await expect(order.getByLabel('采购数量', { exact: true }).first()).toHaveValue('0.333')
  await expect(order.getByLabel('含税单价（元）', { exact: true }).first()).toHaveValue('10.01')
  await expect(order.getByLabel('含税单价（元）', { exact: true }).nth(1)).toHaveValue('20.02')
  await expect(order.getByLabel('供应商', { exact: true })).toHaveValue(String(partnerRow.id))
  await expect(order.getByLabel('交期', { exact: true })).toHaveValue('2026-09-30')
  await expect(order.getByLabel('结算方式', { exact: true })).toHaveValue('month30')
  // 每行先按分四舍五入：0.333 × 10.01 = 3.33，再加 20.02 和 30.03。
  await expect(order).toContainText(/3\.33/)
  await expect(order).toContainText(/53\.38/)
  await page.screenshot({ path: info.outputPath(`bom-purchase-workspace-${info.project.name}.png`), animations: 'disabled' })
  const pending = page.waitForResponse(r => r.url().endsWith('/api/business/purchases/') && r.request().method() === 'POST')
  await order.getByRole('button', { name: '保存采购草稿', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(201)
  const purchase = await read(page, `purchases/${(await response.json()).id}/`)
  expect(purchase.lines.map((r: { item: number }) => r.item).sort()).toEqual([0, 10, 12].map(i => items.results[i].id).sort())
  expect(purchase.status).toBe('draft')
  expect(purchase.payment_term).toBe('month30')
  expect(purchase.payment_days).toBe(30)
  expect(purchase.due_date).toBe('2026-09-30')
  const expectedLines = [
    { index: 0, quantity: '0.333', unit_price: '10.01' },
    { index: 10, quantity: '1.000', unit_price: '20.02' },
    { index: 12, quantity: '1.000', unit_price: '30.03' },
  ]
  for (const expected of expectedLines) {
    const item = items.results[expected.index].id
    const bomLine = demand.lines.find((line: { item: number }) => line.item === item)
    expect(purchase.lines.find((line: { item: number }) => line.item === item)).toMatchObject({
      item, bom_line: bomLine.bom_line, quantity: expected.quantity,
      unit_price: expected.unit_price, due_date: '2026-09-30',
    })
  }
})
