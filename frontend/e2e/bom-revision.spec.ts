import { test, expect, api, businessDate, cancelEditing, login, openRowAction, searchList, submitDialog, type Page } from './fixtures'

const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, text: string) => page.locator('.el-table__body tr:visible').filter({ hasText: text }).first()

// 非标件改图：在途按新图改单、已到货和已领用的旧版进入「旧版待处理」，仓管报废、采购确认改单。
test('BOM 升版后在途按新图改单，旧版在库报废，采购确认新图后才能收货', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const suffix = `${Date.now()}${info.project.name}`
  const admin = await api(page, 'auth/me/')
  const customer = await api(page, 'business/partners/', { kind: 'customer', name: `换版客户${suffix}` }, 201)
  const supplier = await api(page, 'business/partners/', { kind: 'supplier', name: `换版供方${suffix}` }, 201)
  const project = await api(page, 'business/projects/', { name: `换版验收${suffix}`, customer: customer.id, manager: admin.id }, 201)
  const drawing = `DWG-${suffix}`
  const created = await api(page, 'business/items/', { name: `夹爪安装板${suffix}`, specification: '6061 200x80', drawing_number: drawing, drawing_revision: 'A', product_category: '12', part_type: 'custom', unit: 'PCS' }, 201)
  const item = await api(page, `business/items/${created.id}/`)
  const demand = await api(page, `business/projects/${project.id}/demand/`)
  await api(page, `business/projects/${project.id}/revise-bom/`, { expected_revision: demand.revision, lines: [{ item: item.id, quantity: '10', assembly_unit: '上料单元', change_note: '首版' }] })
  const line = (await api(page, `business/projects/${project.id}/demand/`)).lines[0]
  const purchase = await api(page, 'business/purchases/', { project: project.id, supplier: supplier.id, due_date: businessDate(30), lines: [{ item: item.id, bom_line: line.bom_line, quantity: '6', unit_price: '10' }] }, 201)
  await api(page, `business/purchases/${purchase.id}/submit/`, {})
  await api(page, `business/purchases/${purchase.id}/approve/`, { reason: '隔离验收管理员审批例外' })
  const ordered = await api(page, `business/purchases/${purchase.id}/`)
  await api(page, `business/purchases/${purchase.id}/receive/`, { lines: [{ line: ordered.lines[0].id, quantity: '4' }] })
  const stock = (await api(page, `business/stocks/?item=${item.id}`)).results[0]
  await api(page, 'business/stocks/issue/', { project: project.id, stock: stock.id, quantity: '2', reason: '装配领料' })

  // 工程师在项目 BOM 行上一步升版：只填新版本和变更说明。
  await page.goto(`/erp/projects/${project.id}`)
  await page.getByRole('tab', { name: 'BOM', exact: true }).click()
  const bom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await openRowAction(page, bom.locator('.el-table__body tr:visible').filter({ hasText: item.code }).first(), '升版')
  await expect(dialog(page)).toContainText('按新图改单')
  await dialog(page).getByLabel('新图档版本', { exact: true }).fill('B')
  await dialog(page).getByLabel('变更说明', { exact: true }).fill(`ECN-${suffix} 孔位调整`)
  const upgraded = await submitDialog(page, `business/bom/${line.bom_line}/upgrade/`)
  expect(upgraded.created_item).toBe(true)
  expect(upgraded.converted).toEqual([expect.objectContaining({ code: ordered.code, quantity: '2.000', pending: true })])

  // 旧版待处理：在库 2（到货 4 − 已领 2）、已装机 2；仓管报废在库旧版，金额计入项目材料成本。
  const panel = page.getByRole('region', { name: '换版与旧版待处理', exact: true })
  await expect(panel).toContainText(`${item.code}（A 版） → ${upgraded.item_code}（B 版）`)
  await expect(panel).toContainText('在库 2')
  await expect(panel).toContainText('已装机 2')
  await page.screenshot({ path: info.outputPath('bom-revision-panel.png'), fullPage: true, animations: 'disabled' })
  await panel.getByRole('button', { name: '处理 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name: '在库报废', exact: true }).click()
  await expect(dialog(page)).toContainText('计入本项目材料成本')
  await dialog(page).getByLabel('原因', { exact: true }).fill('A 版孔位不对，无法改制')
  const change = (await api(page, `business/projects/${project.id}/obsolete-parts/`)).parts[0].change
  await submitDialog(page, `business/revision-changes/${change}/dispose/`)
  await expect(panel).not.toContainText('在库 2')
  await expect(panel).toContainText('已处理：在库报废 2')
  const scrapped = await api(page, `business/moves/?project=${project.id}&kind=scrap`)
  expect(scrapped.results.map((move: { quantity: string }) => move.quantity)).toEqual(['-2.000'])

  // 已批准采购的旧版余量已转新版：仓库暂不能收，采购按新图确认后才出现在收货列表。
  await page.goto('/erp/purchases')
  await searchList(page, '采购订单', ordered.code)
  await openRowAction(page, row(page, ordered.code), '收货')
  await expect(dialog(page)).toContainText('待采购向供应商确认新图')
  await cancelEditing(dialog(page))
  await openRowAction(page, row(page, ordered.code), '确认换版改单')
  await expect(dialog(page)).toContainText(`由 ${item.code} 转来`)
  await dialog(page).getByLabel('说明', { exact: true }).fill('供应商邮件确认按 B 版加工')
  await submitDialog(page, `business/purchases/${purchase.id}/revision-review/`)
  const confirmed = await api(page, `business/purchases/${purchase.id}/`)
  expect(confirmed.lines.find((l: { item: number }) => l.item === upgraded.item)).toMatchObject({ revision_pending: false, revision_role: 'converted', revision_from: item.code })
  await openRowAction(page, row(page, ordered.code), '收货')
  await expect(dialog(page).getByRole('table', { name: '本次收货明细', exact: true })).toContainText(upgraded.item_code)
})
