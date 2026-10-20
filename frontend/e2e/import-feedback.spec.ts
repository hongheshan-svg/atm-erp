import { test, expect } from '@playwright/test'

// These UI fixtures never reach a database. Real parsing, permissions and rollback
// are exercised by test_import_feedback.py and the existing import service tests.
test('导入纠错与BOM双视图在桌面和手机可操作', async ({ page }, info) => {
  await page.addInitScript(() => { localStorage.setItem('access_token', 'isolated-ui-fixture'); localStorage.setItem('erp.page-size', '10') })
  const project = { id: 7, name: '装配线界面验证项目', code: 'ATM26007', status: 'active', can_edit_bom: true, can_manage: true, equipment_quantity: 1 }
  const lines = [
    { bom_line: 41, item_code: 'M001', item_name: '伺服电机', specification: '750W', assembly_unit: '上料单元', quantity: '4', unit: '台', issued: '0', incoming: '1', available: '1', shortage: '2', required_date: '2026-11-01' },
    { bom_line: 42, item_code: 'M001', item_name: '伺服电机', specification: '750W', assembly_unit: '检测单元', quantity: '2', unit: '台', issued: '0', incoming: '0', available: '0', shortage: '2', required_date: '2026-11-05' },
  ]
  const previewLines = Array.from({ length: 22 }, (_, index) => ({ row: index + 2, item_code: 'M001', item_name: '伺服电机', assembly_unit: `单元${index + 1}`, quantity: index === 21 ? '-2' : '2', specification: '750W' }))
  const writes: string[] = []
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname
    const reply = (data: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    if (route.request().method() !== 'GET') writes.push(path)
    if (path === '/api/auth/me/') return reply({ id: 1, roles: ['admin'], username: 'admin', display_name: '测试管理员' })
    if (path === '/api/business/projects/7/demand/') return reply({ revision: 1, lines })
    if (path === '/api/business/projects/7/') return reply(project)
    if (path === '/api/business/projects/') return reply({ results: [project], count: 1, next: null })
    if (path === '/api/business/projects/7/import-preview/') return reply({ lines: previewLines, errors: [{ row: 23, message: '需求数量：请输入正数。', fields: ['quantity'] }], can_import: false })
    if (path === '/api/business/projects/import-schema/') return reply({ title: '项目', columns: [{ key: 'name', label: '项目名称', table_keys: ['name'] }], entry: '项目列表 → 导入', note: '新增执行项目。' })
    if (path === '/api/business/projects/import-file/') return reply({ file: '这是项目任务模板，请到项目任务导入入口。', template_hint: { code: 'tasks', title: '项目任务', entry: '项目 → 项目任务 → 导入' } }, 400)
    return reply({ results: [], count: 0, next: null })
  })
  await page.goto('/erp/bom?project=7')
  const region = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await expect(region.getByRole('button', { name: '维护 BOM', exact: true })).toBeVisible()
  await expect(region.getByRole('columnheader', { name: '需求数量', exact: true })).toBeVisible()
  await expect(region.getByRole('columnheader', { name: '图号', exact: true })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('bom-prepare.png'), animations: 'disabled', fullPage: true })
  await region.getByLabel('采购缺料', { exact: true }).check()
  await expect(region.getByRole('columnheader', { name: '缺料', exact: true })).toBeVisible()
  await region.getByLabel('选择 M001 上料单元', { exact: true }).check()
  await region.getByLabel('选择 M001 检测单元', { exact: true }).check()
  await expect(region.locator('.bom-selection-bar')).toContainText('已选 2 项')
  await page.screenshot({ path: info.outputPath('bom-shortage.png'), animations: 'disabled', fullPage: true })
  await region.getByRole('button', { name: '导入 BOM', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导入BOM', exact: true })
  await expect(dialog).toContainText('目标项目：装配线界面验证项目（ATM26007）')
  await dialog.locator('input[type=file]').setInputFiles({ name: 'bom.csv', mimeType: 'text/csv', buffer: Buffer.from('界面夹具') })
  await expect(dialog).toContainText('共 22 行，1 行有问题')
  await dialog.getByRole('button', { name: '定位第 23 行', exact: true }).click()
  await expect(dialog.locator('[data-import-row="23"][data-import-field="quantity"]')).toBeFocused()
  await dialog.getByLabel('只看错误行', { exact: true }).check()
  await expect(dialog.locator('.el-table__body tbody tr')).toHaveCount(1)
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: '关闭', exact: true })).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width + 1)
  await page.screenshot({ path: info.outputPath('bom-import-errors.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await page.goto('/erp/projects?resource=projects')
  await page.getByRole('button', { name: '导入导出 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name: '导入', exact: true }).click()
  const projectImport = page.getByRole('dialog', { name: '导入项目', exact: true })
  await projectImport.locator('input[type=file]').setInputFiles({ name: 'tasks.csv', mimeType: 'text/csv', buffer: Buffer.from('界面夹具') })
  await expect(projectImport).toContainText('这是项目任务模板')
  await expect(projectImport.getByRole('link', { name: '前往项目任务导入入口' })).toHaveAttribute('href', '/erp/projects?resource=tasks')
  await expect(projectImport.getByRole('button', { name: '确认导入', exact: true })).toBeDisabled()
  await page.screenshot({ path: info.outputPath('wrong-template.png'), animations: 'disabled' })
  expect(writes).toEqual(['/api/business/projects/7/import-preview/', '/api/business/projects/import-file/'])
})
