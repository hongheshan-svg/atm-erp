import { readFile } from 'node:fs/promises'
import { test, expect, login } from './fixtures'

test('真实表格预览后导入物料，按筛选导出全部结果和报表', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/masterdata')
  const panel = page.getByRole('region', { name: '物料', exact: true })
  await panel.getByRole('button', { name: '导入', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量导入', exact: true })
  const templateEvent = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '下载模板', exact: true }).click()
  const template = await templateEvent
  expect(template.suggestedFilename()).toBe('items-template.xlsx')
  expect((await readFile((await template.path())!)).subarray(0, 2).toString()).toBe('PK')
  const prefix = `IMPORT${Date.now()}`
  const csv = '物料编码,名称,规格,单位\n' + Array.from({ length: 12 }, (_, i) => `${prefix}-${i},导入验收${prefix.slice(6)}-${i},标准,件`).join('\n')
  await dialog.locator('input[type=file]').setInputFiles({ name: 'items.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
  await expect(dialog.getByText('共 12 条，确认时再次校验', { exact: false })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeInViewport({ ratio: 1 })
  await page.screenshot({ path: info.outputPath('import-preview.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(dialog.getByRole('status')).toContainText('成功导入 12 条记录')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await panel.getByRole('searchbox').fill(prefix)
  await panel.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(panel.locator('.record-count')).toHaveText('12')
  await panel.getByLabel('导入导出格式').selectOption('csv')
  const exportedEvent = page.waitForEvent('download')
  await panel.getByRole('button', { name: '导出', exact: true }).click()
  const exported = await exportedEvent
  const content = await readFile((await exported.path())!, 'utf8')
  expect(content.match(new RegExp(prefix, 'g'))).toHaveLength(12)
  await page.goto('/erp/reports')
  const reportEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出', exact: true }).click()
  const report = await reportEvent
  expect(report.suggestedFilename()).toBe('reports.xlsx')
  expect((await readFile((await report.path())!)).subarray(0, 2).toString()).toBe('PK')
})
