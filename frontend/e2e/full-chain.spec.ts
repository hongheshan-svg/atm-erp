import { businessDate } from './fixtures'
import { cancelEditing } from './fixtures'
import { selectRemoteOption } from './remote-select-helpers'
import { test, expect, observePage, expectHttpError, login as loginWithRetry, type Page, type Locator, openRowAction, selectExecutors, choose, submitDialog } from './fixtures'
import { confirmSettlement } from './settlement-helpers'
import { selectRoles } from './role-helpers'
const password = 'Lean-QA-2026-password'
// 业务日期按 Asia/Shanghai 计算，与服务端“今天”一致，不随运行机器时区变化。
const day = (offset = 0) => businessDate(offset)
const dialog = (p: Page) => p.getByRole('dialog')
async function fill(p: Page, label: string, value: string) {
  await dialog(p).getByLabel(label, { exact: true }).fill(value)
}
async function action(p: Page, row: Locator, name: string) {
  await openRowAction(p, row, name)
  await expect(dialog(p)).toBeVisible()
}
// 项目页会记住上次停留的页签；确认任务前回到「任务与工时 → 项目任务」。
async function openProjectTasks(p: Page) {
  await p.reload()
  await p.getByRole('tab', { name: '任务与工时', exact: true }).click()
  await p.getByRole('tab', { name: '项目任务', exact: true }).click()
}
async function projectAction(p: Page, name: string) {
  await p.getByRole('button', { name: '项目操作 ▾', exact: true }).click()
  await p.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(p)).toBeVisible()
}
const row = (p: Page, text: string, region?: string) =>
  (region ? p.getByRole('region', { name: region, exact: true }) : p)
    .locator('.el-table__body tr:visible').filter({ hasText: text }).first()
async function login(p: Page, username: string, pw = password) {
  await loginWithRetry(p, username, pw)
}
async function read(p: Page, path: string) {
  const token = await p.evaluate(() => localStorage.getItem('access_token'))
  const response = await p.request.get('/api/' + path, { headers: { Authorization: `Bearer ${token}` } })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}
async function reason(p: Page, text = '验收测试') {
  await fill(p, '原因 / 说明', text)
}
async function rejectSelfApproval(p: Page, purchase: { id: number; code: string }, overBudget: boolean, screenshotPath: string) {
  const before = await read(p, `business/purchases/${purchase.id}/`)
  const entries = await read(p, `business/entries/?project=${before.project}`)
  await action(p, row(p, purchase.code), '批准采购')
  if (overBudget) {
    await fill(p, '超预算批准原因', '兼任项目经理与采购员仍不得批准本人采购')
    await dialog(p).getByLabel('确认承担本次超预算采购', { exact: true }).check()
  } else await reason(p, '验证本项目经理兼采购员不能批准本人采购')
  const path = `/api/business/purchases/${purchase.id}/${overBudget ? 'approve-over-budget' : 'approve'}/`
  expectHttpError(p, path, 403)
  const response = p.waitForResponse(r => new URL(r.url()).pathname === path && r.request().method() === 'POST')
  await dialog(p).locator('button[type="submit"]').click()
  expect((await response).status()).toBe(403)
  await expect(dialog(p).locator('.el-alert--error')).toContainText('申请人不能审批自己的单据')
  expect(await read(p, `business/purchases/${purchase.id}/`)).toEqual(before)
  expect(await read(p, `business/entries/?project=${before.project}`)).toEqual(entries)
  await p.screenshot({ path: screenshotPath, animations: 'disabled' })
  await cancelEditing(dialog(p))
}

for (const combinedRoles of [false, true]) {
test(combinedRoles ? '项目经理兼采购员同一账号完成销售交接至结项，双岗本人采购禁止自批' : '七角色完成销售交接采购生产分批交付售后与结算', async ({ browser, page }, info) => {
  test.setTimeout(300000)
  const adminPassword = process.env.E2E_ADMIN_PASSWORD
  expect(adminPassword, '必须显式提供隔离测试管理员密码').toBeTruthy()
  const suffix = String(Date.now()).slice(-9)
  const names = {
    item: '电机' + suffix,
    customer: '客户' + suffix,
    supplier: '供应商' + suffix,
    project: (combinedRoles ? '项目采购双岗' : '完整交付') + suffix,
  }
  const roles = ['sales_manager', 'manager', 'purchaser', 'warehouse', 'finance', 'member']
  const people: Record<string, Page> = {}
  const errors: string[] = []
  page.setDefaultTimeout(15000)
  await login(page, 'admin', adminPassword)
  // 各岗位的完整导航由 role-page-audit 逐项核对；这里只确认管理员进入后台后能到达设置页。
  await expect(page.getByRole('navigation', { name: '主导航', includeHidden: true }).getByRole('link', { name: '设置', exact: true, includeHidden: true })).toHaveCount(1)
  await page.goto('/erp/settings')
  for (const role of roles) {
    const samePerson = combinedRoles && role === 'purchaser'
    if (!samePerson) {
    await page.getByRole('button', { name: '新增用户', exact: true }).click()
    await fill(page, '用户名', role + suffix)
    await fill(page, '姓名', role + suffix)
    await selectRoles(dialog(page), combinedRoles && role === 'manager' ? ['manager', 'purchaser'] : [role])
    await fill(page, '小时成本（元）', role === 'member' ? '50' : '0')
    await fill(page, '密码', password)
    await submitDialog(page)
    }
    const context = await browser.newContext({
      baseURL: info.project.use.baseURL,
      viewport: info.project.use.viewport,
      isMobile: info.project.use.isMobile,
      hasTouch: info.project.use.hasTouch,
    })
    const p = await context.newPage()
    p.setDefaultTimeout(15000)
    observePage(p, errors)
    people[role] = p
    await login(p, (samePerson ? 'manager' : role) + suffix)
  }
  const { sales_manager: salesperson, manager, purchaser, warehouse, finance, member } = people
  if (combinedRoles) {
    const identity = await read(manager, 'auth/me/')
    expect(identity.roles.slice().sort()).toEqual(['manager', 'purchaser'])
    expect(identity.management_reports).toBe(false)
    expect((await read(purchaser, 'auth/me/')).id).toBe(identity.id)
    const nav = manager.getByRole('navigation', { name: '主导航', includeHidden: true })
    for (const name of ['项目', '采购']) await expect(nav.getByRole('link', { name, exact: true, includeHidden: true })).toHaveCount(1)
    await expect(nav.getByRole('link', { name: '经营报表', exact: true, includeHidden: true })).toHaveCount(0)
  }
  await purchaser.goto('/erp/masterdata')
  await purchaser.getByRole('button', { name: '新增物料', exact: true }).click()
  await fill(purchaser, '物料名称', names.item)
  await fill(purchaser, '物料编码（留空自动生成）', 'CUSTOM-' + suffix)
  await submitDialog(purchaser)
  await purchaser.getByRole('tab', { name: '客户与供应商', exact: true }).click()
  for (const [kind, name] of [
    ['customer', names.customer],
    ['supplier', names.supplier],
  ]) {
    await purchaser.getByRole('button', { name: '新增往来单位', exact: true }).click()
    await fill(purchaser, '单位名称', name)
    await dialog(purchaser).getByLabel('类型', { exact: true }).selectOption(kind)
    await submitDialog(purchaser)
  }
  await salesperson.goto('/erp/sales')
  await salesperson.getByRole('button', { name: '新建销售', exact: true }).click()
  await fill(salesperson, '销售名称', names.project)
  await choose(salesperson, '客户', names.customer)
  await fill(salesperson, '设备数量', '2')
  await fill(salesperson, '质保月数', '0')
  await submitDialog(salesperson)
  const saleRow = row(salesperson, names.project)
  await action(salesperson, saleRow, '报价')
  await fill(salesperson, '报价金额（元）', '10000')
  await fill(salesperson, '报价说明', '验收测试')
  await submitDialog(salesperson)
  await action(salesperson, saleRow, '编辑销售')
  await fill(salesperson, '需求说明', '确认两台设备及交付范围')
  await reason(salesperson, '补充需求后重新确认报价')
  await submitDialog(salesperson)
  const revisedSale = (await read(salesperson, 'business/sales/?search=' + encodeURIComponent(names.project))).results[0]
  expect(revisedSale.status).toBe('draft')
  expect(Number(revisedSale.quote_amount)).toBe(0)
  expect(revisedSale.project).toBeNull()
  // 编辑后退回草稿：等列表刷新出草稿行的主按钮「报价」再操作。
  await expect(saleRow.getByRole('button', { name: '报价', exact: true })).toBeVisible()
  await action(salesperson, saleRow, '报价')
  await fill(salesperson, '报价金额（元）', '10000')
  await fill(salesperson, '报价说明', '重新确认')
  await submitDialog(salesperson)
  // 列表在对话框关闭后才刷新：等「签约」成为该行主按钮，避免打开旧草稿行的菜单去找签约。
  await expect(saleRow.getByRole('button', { name: '签约', exact: true })).toBeVisible()
  await action(salesperson, saleRow, '签约')
  await fill(salesperson, '合同编号（按签署合同填写）', 'HT-' + suffix)
  await choose(salesperson, '项目负责人', 'manager' + suffix)
  await choose(salesperson, '项目成员', 'member' + suffix)
  await fill(salesperson, '签约日期', day(-2))
  await fill(salesperson, '收款到期日', day())
  await submitDialog(salesperson)
  await expect(salesperson.locator('.el-message')).toHaveCount(0)
  await action(salesperson, saleRow, '查看明细')
  await expect(dialog(salesperson).getByLabel('合同金额（元）', { exact: true })).toHaveValue('10,000.00')
  await expect(dialog(salesperson).getByLabel('合同编号', { exact: true })).toHaveValue('HT-' + suffix)
  await expect(dialog(salesperson).locator('button[type="submit"]')).toHaveCount(0)
  await dialog(salesperson).getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog(salesperson)).not.toBeVisible()
  await salesperson.screenshot({ path: info.outputPath('sales-module.png'), fullPage: true, animations: 'disabled' })
  const signedSale = await read(salesperson, `business/sales/${revisedSale.id}/`)
  const id = signedSale.project
  expect(id).toBeTruthy()
  await manager.goto(`/erp/projects/${id}`)
  await expect(manager.getByRole('heading', { name: names.project, exact: true })).toBeVisible()
  await manager.getByRole('tab', { name: '成本与预算', exact: true }).click()
  await manager.getByRole('button', { name: '设置预算', exact: true }).click()
  await fill(manager, '材料预算（元）', '300')
  await fill(manager, '人工预算（元）', '400')
  await fill(manager, '费用预算（元）', '50')
  await reason(manager, '确定初始项目预算')
  await submitDialog(manager)
  const initialBudget = await read(manager, `business/projects/${id}/cost-analysis/`)
  expect(initialBudget.budget_total).toBe('750.00')
  await manager.getByRole('tab', { name: 'BOM', exact: true }).click()
  const item = (await read(manager, 'business/items/?search=' + encodeURIComponent(names.item))).results[0]
  await manager.getByRole('button', { name: '导入 BOM', exact: true }).click()
  await manager
    .getByRole('dialog', { name: '导入BOM', exact: true })
    .locator('input[type=file]')
    .setInputFiles({
      name: 'bom.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`物料编码,数量,变更说明\n${item.code},4,初版\n`),
    })
  await manager.getByRole('button', { name: '确认导入', exact: true }).click()
  await submitDialog(manager)
  await purchaser.goto(`/erp/projects/${id}`)
  await purchaser.getByRole('tab', { name: 'BOM', exact: true }).click()
  // Selecting before the demand rows land silently selects nothing, leaving the purchase picker empty.
  await expect(purchaser.locator('.el-table__body tr:visible').filter({ hasText: item.code })).toBeVisible()
  // 兼任项目经理的采购员默认落在「编制用料」，缺料下单在「采购缺料」视图。
  const shortageView = purchaser.getByRole('radio', { name: '采购缺料', exact: true })
  if (await shortageView.isVisible()) await shortageView.check()
  await purchaser.getByRole('button', { name: '全选筛选结果', exact: true }).click()
  await purchaser.getByRole('button', { name: '从 BOM 多选下单', exact: true }).click()
  const purchaseWorkspace = purchaser.getByRole('region', { name: '从 BOM 多选下单', exact: true })
  const purchaseDraft = purchaseWorkspace.getByRole('region', { name: '采购草稿', exact: true })
  await selectRemoteOption(purchaseDraft.getByLabel('供应商', { exact: true }), { text: names.supplier })
  await purchaseDraft.getByLabel('交期', { exact: true }).fill(day())
  await purchaseDraft.getByLabel('含税单价（元）', { exact: true }).fill('100')
  const purchaseSaved = purchaser.waitForResponse(r => r.url().endsWith('/api/business/purchases/') && r.request().method() === 'POST')
  await purchaseDraft.getByRole('button', { name: '保存采购草稿', exact: true }).click()
  const purchaseResponse = await purchaseSaved
  expect(purchaseResponse.status(), await purchaseResponse.text()).toBe(201)
  await expect(purchaseWorkspace).not.toBeVisible()
  let purchases = (await read(purchaser, `business/purchases/?project=${id}`)).results
  const po = purchases[0]
  await purchaser.goto('/erp/purchases')
  await action(purchaser, row(purchaser, po.code), '提交采购')
  await submitDialog(purchaser)
  if (combinedRoles) await rejectSelfApproval(purchaser, po, true, info.outputPath('self-approval-over-budget-denied.png'))
  await page.goto('/erp/purchases')
  await action(page, row(page, po.code), '批准采购')
  await expect(dialog(page).getByRole('heading', { name: '超预算采购审批' })).toBeVisible()
  await page.screenshot({ path: info.outputPath('over-budget-approval.png'), animations: 'disabled' })
  await fill(page, '超预算批准原因', '管理员复核预算调整人的申请，批准本次超额')
  await dialog(page).getByLabel('确认承担本次超预算采购', { exact: true }).check()
  await submitDialog(page)
  await manager.goto(`/erp/projects/${id}?tab=cost&section=budget`)
  await expect(manager.getByRole('region', { name: '项目预算与成本管控' }).getByRole('alert')).toContainText('超预算')
  await manager.getByRole('button', { name: '设置预算', exact: true }).click()
  await fill(manager, '材料预算（元）', '500')
  await reason(manager, '确认追加材料预算并保留修改依据')
  await submitDialog(manager)
  await manager.goto('/erp/purchases')
  await finance.goto('/erp/finance')
  await confirmSettlement(finance, manager, row(finance, po.code, '应收应付与费用'), true)
  await action(finance, row(finance, po.code, '应收应付与费用'), '登记收付款')
  await reason(finance)
  await submitDialog(finance)
  await finance.getByRole('tab', { name: '收付款流水', exact: true }).click()
  await action(finance, row(finance, po.code, '收付款流水'), '冲销付款')
  await reason(finance, '更正付款登记')
  await submitDialog(finance)
  const paymentRows = finance.getByRole('region', { name: '收付款流水', exact: true }).locator('.el-table__body tr:visible').filter({ hasText: po.code })
  await expect(paymentRows.filter({ hasText: '已冲销' })).toHaveCount(1)
  await expect(paymentRows.filter({ hasText: '冲销记录' })).toHaveCount(1)
  const paymentMenuTrigger = paymentRows.first().getByRole('button', { name: '操作 ▾', exact: true })
  await paymentMenuTrigger.click()
  await expect(finance.getByRole('menuitem', { name: '冲销付款', exact: true })).toHaveCount(0)
  const paymentMenuId = await paymentMenuTrigger.getAttribute('aria-controls')
  expect(paymentMenuId).toBeTruthy()
  await expect(finance.locator(`[id="${paymentMenuId}"]`).getByRole('menuitem', { name: '补录凭证', exact: true })).toBeVisible()
  await finance.keyboard.press('Escape')
  await finance.getByRole('tab', { name: '应收应付与费用', exact: true }).click()
  await confirmSettlement(finance, manager, row(finance, po.code, '应收应付与费用'), true)
  await action(finance, row(finance, po.code, '应收应付与费用'), '登记收付款')
  await reason(finance, '重新登记付款')
  await submitDialog(finance)
  await warehouse.goto('/erp/purchases')
  await action(warehouse, row(warehouse, po.code), '查看明细')
  await expect(dialog(warehouse).getByRole('columnheader', { name: '含税单价（元）', exact: true })).toHaveCount(0)
  const warehousePurchase = await read(warehouse, `business/purchases/${po.id}/`)
  expect(warehousePurchase.lines).toHaveLength(1)
  for (const line of warehousePurchase.lines) expect(line).not.toHaveProperty('unit_price')
  await dialog(warehouse).getByRole('button', { name: '关闭', exact: true }).click()
  await action(warehouse, row(warehouse, po.code), '收货')
  await fill(warehouse, '数量', '3')
  await fill(warehouse, '送货单号 / 备注', '验收测试')
  await submitDialog(warehouse)
  await purchaser.reload()
  await action(purchaser, row(purchaser, po.code), '取消未收余量')
  await fill(purchaser, '本次取消数量', '1')
  await reason(purchaser)
  await submitDialog(purchaser)
  await finance.reload()
  await confirmSettlement(finance, finance, row(finance, po.code, '应收应付与费用'))
  await action(finance, row(finance, po.code, '应收应付与费用'), '退款')
  await reason(finance)
  await submitDialog(finance)
  await purchaser.getByRole('button', { name: '新建采购', exact: true }).click()
  await fill(purchaser, '交期', day())
  await choose(purchaser, '项目', names.project)
  await choose(purchaser, '供应商', names.supplier)
  await choose(purchaser, '物料', names.item)
  await fill(purchaser, '数量', '2')
  await fill(purchaser, '含税单价（元）', '100')
  // BOM 需求 4、首单已到货 3，本单 2 件超出缺口 1 件（后面保内售后领用的备件），手工采购须写明超 BOM 原因。
  await fill(purchaser, '超 BOM 采购原因', '保内售后备件，超出 BOM 1 件')
  await submitDialog(purchaser)
  purchases = (await read(purchaser, `business/purchases/?project=${id}`)).results
  const po2 = purchases.find((p: { id: number }) => p.id !== po.id)
  await action(purchaser, row(purchaser, po2.code), '提交采购')
  await submitDialog(purchaser)
  await manager.reload()
  if (combinedRoles) await rejectSelfApproval(manager, po2, false, info.outputPath('self-approval-within-budget-denied.png'))
  const secondApprover = combinedRoles ? page : manager
  await secondApprover.goto('/erp/purchases')
  await action(secondApprover, row(secondApprover, po2.code), '批准采购')
  await submitDialog(secondApprover)
  await warehouse.reload()
  // 正常到货的说明选填：不填直接收货，服务端按「采购收货」记录。
  await action(warehouse, row(warehouse, po2.code), '收货')
  await submitDialog(warehouse)
  await manager.goto(`/erp/projects/${id}?tab=tasks`)
  for (const [kind, title] of [
    ['design', '设计'],
    ['assembly', '装配'],
    ['test', '调试'],
  ]) {
    await manager.getByRole('button', { name: '新建任务', exact: true }).click()
    await dialog(manager).getByLabel('阶段', { exact: true }).selectOption(kind)
    await fill(manager, '任务名称', title + suffix)
    await selectExecutors(manager, dialog(manager), ['member' + suffix])
    await submitDialog(manager)
  }
  await member.goto(`/erp/projects/${id}`)
  const memberNav = member.getByRole('navigation', { name: '主导航', includeHidden: true })
  await expect(memberNav.getByRole('link', { name: '项目', exact: true, includeHidden: true })).toHaveCount(1)
  for (const hidden of ['采购', '收付款', '销售']) await expect(memberNav.getByRole('link', { name: hidden, exact: true, includeHidden: true })).toHaveCount(0)
  await expect(member.getByLabel('项目成本', { exact: true })).toHaveCount(0)
  expect((await read(member, 'business/projects/')).results.map((p: { id: number }) => p.id)).toEqual([id])
  const memberToken = await member.evaluate(() => localStorage.getItem('access_token'))
  for (const path of ['purchases/', 'entries/', `projects/${id}/cost/`]) {
    const denied = await member.request.get('/api/business/' + path, {
      headers: { Authorization: `Bearer ${memberToken}` },
    })
    expect(denied.status()).toBe(403)
  }
  // v1.8.24 起执行人只查看进度；完成确认和工时登记由专业主管负责，未设主管时由项目经理负责。
  await member.getByRole('tab', { name: '项目任务', exact: true }).click()
  // 行内只剩一项动作时直接显示为文字按钮、不套「操作 ▾」菜单；手机名称格里也没有主按钮。
  const memberTask = row(member, '设计' + suffix)
  await expect(memberTask.locator('.row-actions').getByRole('button')).toHaveText(['查看工时'])
  await expect(memberTask.getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  await expect(memberTask.locator('.mobile-primary-action')).toHaveCount(0)
  await manager.reload()
  for (const title of ['设计', '装配', '调试']) {
    await action(manager, row(manager, title + suffix), '完成任务')
    await fill(manager, '完成说明', '验收测试')
    await submitDialog(manager)
    await action(manager, row(manager, title + suffix), '登记工时')
    await fill(manager, '工时', title === '设计' ? '3' : '1')
    await fill(manager, '工作内容', '验收测试')
    await submitDialog(manager)
  }
  await manager.getByRole('tab', { name: '工时记录', exact: true }).click()
  const timeRows = manager.getByRole('region', { name: '工时记录' })
  await action(manager, timeRows.locator('.el-table__body tr:visible').last(), '更正工时')
  await fill(manager, '更正后工时', '2')
  await reason(manager, '更正设计工时')
  await submitDialog(manager)
  const reversedTime = timeRows.locator('.el-table__body tr:visible').filter({ hasText: '已冲销' })
  await expect(reversedTime).toHaveCount(1)
  await expect(reversedTime.getByRole('button', { name: '操作 ▾', exact: true })).toHaveCount(0)
  await expect(reversedTime.getByRole('button', { name: '更正工时', exact: true })).toHaveCount(0)
  await manager.reload()
  await projectAction(manager, '发货')
  // 推进检查在打开发货时就列出全部缺项（这里是领料不足），不再等填完表单提交后逐条报错。
  await expect(dialog(manager).locator('.action-blocker')).toContainText('领料')
  await expect(dialog(manager).locator('button[type="submit"]')).toHaveCount(0)
  await cancelEditing(dialog(manager))
  await warehouse.goto('/erp/inventory')
  await action(warehouse, row(warehouse, names.item, '现有库存'), '领料')
  await choose(warehouse, '项目', names.project)
  await fill(warehouse, '数量', '4')
  await reason(warehouse)
  await submitDialog(warehouse)
  for (let i = 0; i < 2; i++) {
    await manager.reload()
    await projectAction(manager, '发货')
    await fill(manager, '日期', day(-1))
    await choose(manager, '安装人', 'member' + suffix)
    await submitDialog(manager)
    const deliveries = (await read(manager, `business/deliveries/?project=${id}`)).results
    const delivery = deliveries[0]
    await openProjectTasks(manager)
    const installRow = row(manager, delivery.code + ' 安装')
    await action(manager, installRow, '登记工时')
    await fill(manager, '工时', '1')
    await fill(manager, '工作内容', '验收测试')
    await submitDialog(manager)
    await action(manager, installRow, '完成任务')
    // 验收日期不能早于安装完成日期：安装与发货、验收同为昨天。
    await fill(manager, '实际完成日期', day(-1))
    await fill(manager, '完成说明', '验收测试')
    await submitDialog(manager)
    await manager.getByRole('tab', { name: '交付与售后', exact: true }).click()
    await action(manager, row(manager, delivery.code), '验收')
    await fill(manager, '日期', day(-1))
    await fill(manager, '验收说明', '验收测试')
    await submitDialog(manager)
  }
  const delivery = (await read(manager, `business/deliveries/?project=${id}`)).results[0]
  for (const [title, date, fee] of [
    ['免费售后', day(-1), '0'],
    ['收费售后', day(), '300'],
  ]) {
    await projectAction(manager, '登记售后')
    await choose(manager, '交付批次', delivery.code)
    await fill(manager, '日期', date)
    await fill(manager, '售后事项', title + suffix)
    // 售后只指派一名执行人，是单选人员字段；项目任务的执行人才是多选。
    await choose(manager, '执行人', 'member' + suffix)
    await fill(manager, '收费金额（元）', fee)
    if (Number(fee) > 0) await fill(manager, '客户付款到期日', day())
    await submitDialog(manager)
    if (fee === '0') {
      await warehouse.reload()
      await action(warehouse, row(warehouse, names.item, '现有库存'), '领料')
      await choose(warehouse, '项目', names.project)
      await choose(warehouse, '售后任务（生产领料留空）', title + suffix)
      await fill(warehouse, '数量', '1')
      await reason(warehouse)
      await submitDialog(warehouse)
    }
    await openProjectTasks(manager)
    await action(manager, row(manager, title + suffix), '登记工时')
    await fill(manager, '工时', '1')
    await fill(manager, '工作内容', '验收测试')
    await submitDialog(manager)
    await action(manager, row(manager, title + suffix), '完成任务')
    // 完成说明选填：留空时服务端记为「完成任务」。
    await submitDialog(manager)
  }
  await finance.reload()
  await finance.getByRole('button', { name: '登记费用', exact: true }).click()
  await choose(finance, '项目', names.project)
  await fill(finance, '费用名称', '差旅' + suffix)
  await fill(finance, '金额（元）', '50')
  await fill(finance, '付款到期日', day())
  await submitDialog(finance)
  await manager.reload()
  await projectAction(manager, '结项')
  // 未结清款项在打开结项时就列出，提交按钮不出现；服务端结项仍按同一组检查拒绝。
  await expect(dialog(manager).locator('.action-blocker')).toContainText('款项全部结清')
  await expect(dialog(manager).locator('button[type="submit"]')).toHaveCount(0)
  await cancelEditing(dialog(manager))
  expect((await manager.request.post(`/api/business/projects/${id}/close/`, {
    headers: { Authorization: `Bearer ${await manager.evaluate(() => localStorage.getItem('access_token'))}`, 'Idempotency-Key': crypto.randomUUID() },
    data: { reason: '绕过界面直接结项' },
  })).status()).toBe(409)
  const entries = (await read(finance, `business/entries/?project=${id}`)).results
  for (const entry of entries.filter((e: { balance: string }) => Number(e.balance) > 0)) {
    await finance.reload()
    const target = finance
      .getByRole('region', { name: '应收应付与费用' })
      .locator('.el-table__body tr:visible')
      .filter({ hasText: names.project })
      .filter({ hasText: entry.title })
      .first()
    if (entry.purchase) await confirmSettlement(finance, finance, target)
    await action(finance, target, '登记收付款')
    await reason(finance)
    await submitDialog(finance)
  }
  expect(await read(manager, `business/projects/${id}/cost/`)).toEqual({
    materials: '500.00',
    labor: '400.00',
    expenses: '50.00',
    purchase_return_variance: '0.00',
    total: '950.00',
  })
  const finalBudget = await read(manager, `business/projects/${id}/cost-analysis/`)
  expect(finalBudget.budget_total).toBe('950.00')
  expect(finalBudget.actual_total).toBe('950.00')
  expect(finalBudget.committed_total).toBe('0.00')
  expect(finalBudget.purchase_net).toBe('500.00')
  expect(finalBudget.over_budget).toBe(false)
  await manager.reload()
  await projectAction(manager, '结项')
  await reason(manager)
  await submitDialog(manager)
  await expect(manager.getByText('已结项', { exact: false }).first()).toBeVisible()
  const progress = await read(salesperson, `business/sales/${revisedSale.id}/progress/`)
  expect(progress.project_status).toBe('closed')
  expect(progress.deliveries).toHaveLength(2)
  expect(progress.deliveries.every((delivery: { accepted_date: string }) => !!delivery.accepted_date)).toBe(true)
  expect(progress.receivables).toHaveLength(2)
  expect(progress.receivables.every((entry: { balance: string }) => entry.balance === '0.00')).toBe(true)
  expect(progress.receivables.reduce((sum: number, entry: { paid: string }) => sum + Number(entry.paid), 0)).toBe(10300)
  // 进度接口只返回状态、交付、应收及两项界面标记（金额是否可见、进度所属项目），不带成本类字段。
  expect(Object.keys(progress).sort()).toEqual(['amounts_visible', 'deliveries', 'progress_project', 'project_status', 'receivables'])
  expect(progress.amounts_visible).toBe(true)
  expect(progress.progress_project).toBe(id)
  await salesperson.reload()
  await action(salesperson, row(salesperson, names.project), '交付与回款')
  await expect(dialog(salesperson).getByLabel('项目状态', { exact: true })).toHaveValue('已结项')
  await expect(dialog(salesperson).locator('button[type="submit"]')).toHaveCount(0)
  await salesperson.screenshot({ path: info.outputPath('sales-completed-progress.png'), fullPage: true, animations: 'disabled' })
  await dialog(salesperson).getByRole('button', { name: '关闭', exact: true }).click()
  await projectAction(manager, '重新打开')
  await reason(manager)
  await submitDialog(manager)
  if (combinedRoles) {
    await projectAction(manager, '结项')
    await reason(manager, '双岗完整链复核通过后再次结项')
    await submitDialog(manager)
    const finalProject = await read(manager, `business/projects/${id}/`)
    const finalEntries = (await read(finance, `business/entries/?project=${id}`)).results
    expect(finalProject.status).toBe('closed')
    expect(finalEntries).toHaveLength(5)
    expect(finalEntries.every((entry: { balance: string }) => Number(entry.balance) === 0)).toBe(true)
    await info.attach('manager-purchaser-chain-result', {
      body: JSON.stringify({
        identity: await read(manager, 'auth/me/'),
        project: { id, code: finalProject.code, name: names.project, status: finalProject.status },
        purchases: (await read(manager, `business/purchases/?project=${id}`)).results,
        cost: await read(manager, `business/projects/${id}/cost/`),
        costAnalysis: finalBudget,
        entries: finalEntries,
        salesProgress: progress,
        selfApprovalDenied: ['over-budget', 'within-budget'],
      }, null, 2), contentType: 'application/json',
    })
    await manager.getByRole('tab', { name: '成本与预算', exact: true }).click()
    await expect(manager.getByRole('region', { name: '项目预算与成本管控' })).toBeVisible()
  }
  await expect(manager.locator('.el-message')).toHaveCount(0)
  await manager.screenshot({ path: info.outputPath('completed-chain.png'), fullPage: true })
  await manager.setViewportSize({ width: 390, height: 844 })
  await manager.screenshot({ path: info.outputPath('completed-chain-mobile.png'), fullPage: true })
  expect(errors).toEqual([])
  for (const p of Object.values(people)) await p.context().close()
})
}
