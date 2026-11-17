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
  // 提交前逐项写明旧版去向，数字与提交后的「旧版待处理」一致。
  await expect(dialog(page)).toContainText(`${ordered.code} 2 转为新版，待采购向供应商确认后才能收货`)
  await expect(dialog(page)).toContainText('换版后旧版 已装机 2、在库 2 超出需求')
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

// 反复改图：别的项目已升到新版时，旧版行标出新版并可一键换成已有新版；已归档合同的采购改单后提醒重签。
test('别的项目已升版时旧版行标出新版并一键换成已有新版，已归档合同的采购改单后提醒重签', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const listing = await (await page.request.get('/api/core/company/', { headers })).json()
  const company = (listing.results || listing)[0]
  const oldCompany = { name: company.name, address: company.address, phone: company.phone }
  const configured = await page.request.patch('/api/core/company/1/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { address: '隔离测试采购方地址', phone: '000-12345' } })
  expect(configured.ok()).toBeTruthy()
  try {
    const suffix = `${Date.now()}${info.project.name}`
    const admin = await api(page, 'auth/me/')
    const customer = await api(page, 'business/partners/', { kind: 'customer', name: `版本链客户${suffix}` }, 201)
    const supplier = await api(page, 'business/partners/', { kind: 'supplier', name: `版本链供方${suffix}`, address: '供方地址', phone: '000-67890' }, 201)
    const first = await api(page, 'business/projects/', { name: `先升版${suffix}`, customer: customer.id, manager: admin.id }, 201)
    const second = await api(page, 'business/projects/', { name: `仍用旧版${suffix}`, customer: customer.id, manager: admin.id }, 201)
    const created = await api(page, 'business/items/', { name: `检测治具底板${suffix}`, specification: 'A3 钢板', drawing_number: `DWG-C-${suffix}`, drawing_revision: 'A', product_category: '12', part_type: 'custom', unit: 'PCS' }, 201)
    const item = await api(page, `business/items/${created.id}/`)
    const lines: Record<number, number> = {}
    for (const project of [first, second]) {
      const demand = await api(page, `business/projects/${project.id}/demand/`)
      await api(page, `business/projects/${project.id}/revise-bom/`, { expected_revision: demand.revision, lines: [{ item: item.id, quantity: '4', assembly_unit: '检测单元', change_note: '首版' }] })
      lines[project.id] = (await api(page, `business/projects/${project.id}/demand/`)).lines[0].bom_line
    }
    // 第二个项目已下单并归档了签署合同。
    const purchase = await api(page, 'business/purchases/', { project: second.id, supplier: supplier.id, due_date: businessDate(30), lines: [{ item: item.id, bom_line: lines[second.id], quantity: '4', unit_price: '10' }] }, 201)
    await api(page, `business/purchases/${purchase.id}/submit/`, {})
    await api(page, `business/purchases/${purchase.id}/approve/`, { reason: '隔离验收管理员审批例外' })
    const detailCode = (await api(page, `business/purchases/${purchase.id}/`)).code as string
    const uploaded = await page.request.post('/api/business/documents/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, multipart: { purchase: String(purchase.id), category: 'contract', file: { name: '隔离测试签署样本.txt', mimeType: 'text/plain', buffer: Buffer.from('自动验收样本') } } })
    expect(uploaded.status()).toBe(201)
    const current = await api(page, `business/purchases/${purchase.id}/contract-preview/?version=current`)
    await api(page, `business/purchases/${purchase.id}/archive-contract/`, { expected_snapshot: current.snapshot_hash, document: (await uploaded.json()).id, delivery_address: '隔离验收收货地点', confirmed: true }, 201)
    // 第一个项目先升到 B 版。
    const upgraded = await api(page, `business/bom/${lines[first.id]}/upgrade/`, { drawing_revision: 'B', change_note: `ECN-${suffix} 加厚` })

    // 第二个项目仍用 A 版：行上标「有新版 B」，升版直接填好 B，提示在途怎么转。
    await page.goto(`/erp/projects/${second.id}`)
    await page.getByRole('tab', { name: 'BOM', exact: true }).click()
    const bom = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
    const oldRow = bom.locator('.el-table__body tr:visible').filter({ hasText: item.code }).first()
    await expect(oldRow).toContainText('有新版 B')
    await openRowAction(page, oldRow, '升版（换成已有 B 版）')
    await expect(dialog(page)).toContainText(`该图已有新版 B 版（${upgraded.item_code}）`)
    await expect(dialog(page)).toContainText(detailCode)
    await expect(dialog(page)).toContainText('转为新版，待采购向供应商确认后才能收货')
    await expect(dialog(page).getByLabel('新图档版本', { exact: true })).toHaveValue('B')
    await dialog(page).getByLabel('变更说明', { exact: true }).fill(`跟进 ECN-${suffix}`)
    await page.screenshot({ path: info.outputPath('upgrade-to-existing.png'), fullPage: true, animations: 'disabled' })
    const followed = await submitDialog(page, `business/bom/${lines[second.id]}/upgrade/`)
    expect(followed.created_item).toBe(false)
    expect(followed.item_code).toBe(upgraded.item_code)
    await expect(bom.locator('.el-table__body tr:visible').filter({ hasText: upgraded.item_code }).first()).not.toContainText('有新版')

    // 采购按新图确认（改价）：已归档合同的单子在工作台和合同页提醒重签。
    const detail = await api(page, `business/purchases/${purchase.id}/`)
    const converted = detail.lines.find((line: { revision_pending: boolean }) => line.revision_pending)
    const reviewed = await api(page, `business/purchases/${purchase.id}/revision-review/`, { line: converted.id, decision: 'confirm', unit_price: '12', reason: '供应商按 B 版重新报价' })
    expect(reviewed.contract_version).toBe(1)
    const workbench = await api(page, 'business/workbench/?bucket=contract_updates')
    expect(workbench.contract_updates.results.map((r: { id: number }) => r.id)).toContain(purchase.id)
    await page.goto(`/erp/purchases/${purchase.id}/contract`)
    const changed = page.locator('.contract-changed')
    await expect(changed).toContainText('合同内容自已归档第 1 版后已变化')
    await expect(changed).toContainText(`${item.code}（A 版） 数量 4 → 0`)
    await expect(changed).toContainText(`新增 ${upgraded.item_code}（B 版）`)
    await expect(changed).toContainText('单价 12.00')
    await page.screenshot({ path: info.outputPath('contract-changed.png'), fullPage: true, animations: 'disabled' })
    // 从提示条直接切到改单后的当前合同核对，再归档新版本。
    await changed.getByRole('button', { name: '查看改单后的当前合同', exact: true }).click()
    await expect(page.getByRole('article')).toContainText(upgraded.item_code)
    await expect(page.getByRole('button', { name: '归档新版本', exact: true })).toBeVisible()

    // 物料的版本记录：同图号全部版本和两个项目的换版原因。
    await page.goto('/erp/masterdata')
    await page.getByRole('tab', { name: '物料', exact: true }).click()
    await searchList(page, '物料', item.code)
    const itemRow = row(page, item.code)
    await expect(itemRow).toContainText('已有新版 B')
    await openRowAction(page, itemRow, '版本记录')
    await expect(dialog(page)).toContainText(`当前最新为 B 版（${upgraded.item_code}）`)
    await expect(dialog(page)).toContainText(`ECN-${suffix} 加厚`)
    await expect(dialog(page)).toContainText(`跟进 ECN-${suffix}`)
  } finally {
    const restored = await page.request.patch('/api/core/company/1/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: oldCompany })
    expect(restored.ok()).toBeTruthy()
  }
})
