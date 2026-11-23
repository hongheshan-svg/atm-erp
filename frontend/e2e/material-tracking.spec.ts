import { test, expect, api, businessDate, login, openRowAction, searchList, submitDialog, type Page } from './fixtures'
import { selectRemoteOption } from './remote-select-helpers'
const dialog = (page: Page) => page.getByRole('dialog')

test('物料跟踪：跨项目一行看清需求、采购、到货、领料与领料人，BOM 外采购也列出', async ({ page, session }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const suffix = `${Date.now()}${info.project.name}`
  const admin = await api(page, 'auth/me/')
  const customer = await api(page, 'business/partners/', { kind: 'customer', name: `跟踪客户${suffix}` }, 201)
  const supplier = await api(page, 'business/partners/', { kind: 'supplier', name: `跟踪供方${suffix}` }, 201)
  const project = await api(page, 'business/projects/', { name: `物料跟踪${suffix}`, customer: customer.id, manager: admin.id }, 201)
  let plate = await api(page, 'business/items/', { name: `气缸安装板${suffix}`, specification: '6061 板厚8mm', drawing_number: `TRK-${suffix}`, drawing_revision: 'B', product_category: '11', part_type: 'custom', unit: 'PCS' }, 201)
  let tie = await api(page, 'business/items/', { name: `扎带${suffix}`, specification: `3x100-${suffix}`, brand: '通用', product_category: '21', part_type: 'standard', unit: '包' }, 201)
  // 新建物料的返回不含完整资料，重读一次拿系统编码。
  plate = await api(page, `business/items/${plate.id}/`)
  tie = await api(page, `business/items/${tie.id}/`)
  const demand = await api(page, `business/projects/${project.id}/demand/`)
  await api(page, `business/projects/${project.id}/revise-bom/`, { expected_revision: demand.revision, lines: [{ item: plate.id, quantity: '4', assembly_unit: '上料单元', change_note: '首版' }] })
  const bom = await api(page, `business/projects/${project.id}/demand/`)
  let order = await api(page, 'business/purchases/', { project: project.id, supplier: supplier.id, due_date: businessDate(20), lines: [{ item: plate.id, bom_line: bom.lines[0].bom_line, quantity: '4', unit_price: '35' }] }, 201)
  await api(page, `business/purchases/${order.id}/submit/`, {})
  await api(page, `business/purchases/${order.id}/approve/`, { reason: '物料跟踪验收管理员审批例外' })
  order = await api(page, `business/purchases/${order.id}/`)
  await api(page, `business/purchases/${order.id}/receive/`, { lines: [{ line: order.lines[0].id, quantity: '4' }], reason: `送货单 SH-${suffix}` })
  // 项目后来另外买的零星物料：不在 BOM，也要出现在跟踪表里。
  const extra = await api(page, 'business/purchases/', { project: project.id, supplier: supplier.id, due_date: businessDate(10), over_bom_reason: '现场补料', lines: [{ item: tie.id, quantity: '10', unit_price: '1.5' }] }, 201)
  await api(page, `business/purchases/${extra.id}/submit/`, {})
  const extraCode = (await api(page, `business/purchases/${extra.id}/`)).code

  const warehouse = await api(page, 'auth/users/', { username: `whtrack${suffix}`, display_name: '仓管跟踪', roles: ['warehouse'], password: 'Warehouse-Track-Only-2026' }, 201)
  const wh = await session(warehouse.username, 'Warehouse-Track-Only-2026')
  // 领料时记下实际来领料的人。
  await wh.goto('/erp/inventory?section=stocks&project=all'); await searchList(wh, '现有库存', plate.code)
  await openRowAction(wh, wh.locator('.el-table__body tr:visible').filter({ hasText: plate.code }).first(), '领料')
  await selectRemoteOption(dialog(wh).getByLabel('项目', { exact: true }), { id: project.id })
  await dialog(wh).getByRole('table', { name: '本次出库明细', exact: true }).getByLabel('数量', { exact: true }).fill('2')
  await dialog(wh).getByLabel('领料人', { exact: true }).fill('装配班 张师傅')
  await submitDialog(wh, 'business/stocks/issue/')
  const slip = (await api(wh, `business/issue-slips/?project=${project.id}`)).results[0]
  expect(slip.recipient).toBe('装配班 张师傅')

  await wh.goto(`/erp/tracking?project=${project.id}`)
  const panel = wh.getByRole('region', { name: '物料跟踪表', exact: true })
  await expect(panel.locator('.record-count')).toHaveText('2')
  const mobile = info.project.name === 'mobile'
  const rows = panel.locator(mobile ? '.tracking-cards li' : '.el-table__body tr:visible')
  const plateRow = rows.filter({ hasText: plate.code }).first()
  const tieRow = rows.filter({ hasText: tie.name }).first()
  if (mobile) {
    await expect(plateRow).toContainText('需求 4 · 已采购 4 · 已收 4 · 已领 2 · 缺料 0')
    await expect(tieRow).toContainText('不在 BOM')
    const viewport = await wh.evaluate(() => ({ body: document.body.scrollWidth, visible: document.documentElement.clientWidth }))
    expect(viewport.body, JSON.stringify(viewport)).toBeLessThanOrEqual(viewport.visible)
  } else {
    for (const text of ['待领料', order.code, '装配班 张师傅', `送货单 SH-${suffix}`, slip.code, '上料单元']) await expect(plateRow).toContainText(text)
    for (const text of ['不在 BOM', '待批采购', extraCode]) await expect(tieRow).toContainText(text)
    // 仓管能看采购单号和供应商，看不到单价金额。
    const headers = await panel.locator('.el-table__header th').allInnerTexts()
    expect(headers.map(text => text.trim())).toEqual(expect.arrayContaining(['采购单号', '供应商', '领料人', '已领', '缺料']))
    expect(headers.map(text => text.trim())).not.toContain('单价')
    await wh.screenshot({ path: info.outputPath('material-tracking.png'), fullPage: true, animations: 'disabled' })
    // 领料单号跳到可打印的领料单，单头写着领料人。
    await plateRow.getByRole('link', { name: slip.code, exact: true }).click()
    await expect(wh.getByRole('article', { name: '领料单' })).toContainText('装配班 张师傅')
    await wh.goBack()
  }
  await panel.getByRole('group', { name: '跟踪状态' }).getByRole('button', { name: '待批采购', exact: true }).click()
  await expect(panel.locator('.record-count')).toHaveText('1')
  await expect(rows.filter({ hasText: tie.name })).toHaveCount(1)
  await expect(rows.filter({ hasText: plate.code })).toHaveCount(0)
  const pending = wh.waitForEvent('download')
  await panel.getByRole('button', { name: '导出 Excel', exact: true }).click()
  const file = await pending
  expect(file.suggestedFilename()).toMatch(/^物料跟踪-.*\.xlsx$/)
})
