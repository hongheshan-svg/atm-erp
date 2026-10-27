import { readFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { test, expect, login } from './fixtures'

test('BOM筛选81项标准件跨页导出保持准确，勾选与筛选范围分开且同料多单元不合并', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }, suffix = String(Date.now())
  async function post(path: string, data: object) {
    const result = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(result.status(), await result.text()).toBeLessThan(300)
    return result.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const partner = await post('partners/', { name: `BOM导出验收${suffix}`, kind: 'both' })
  const project = await post('projects/', { name: `BOM按选择导出${suffix}`, customer: partner.id, manager: me.id })
  const lines = []
  for (let i = 0; i < 83; i++) {
    const item = await post('items/', { code: `00${suffix}-${i}`, name: `导出测试物料${i}-${suffix}`, specification: '按图加工', unit: '件', brand: i < 80 ? '标准品牌' : '非标品牌', part_type: i < 80 ? 'standard' : 'custom', product_category: i < 80 ? '21' : '11', ...(i < 80 ? {} : { drawing_number: `DRAW-${suffix}-${i}` }) })
    lines.push({ item: item.id, quantity: '2.5', assembly_unit: '上料单元' })
  }
  lines.push({ ...lines[0]!, assembly_unit: '检测单元' })
  const initial = await (await page.request.get(`/api/business/projects/${project.id}/demand/`, { headers })).json()
  await post(`projects/${project.id}/revise-bom/`, { expected_revision: initial.revision, lines })
  const demand = await (await page.request.get(`/api/business/projects/${project.id}/demand/`, { headers })).json()
  const standards = demand.lines.filter((line: { part_type: string }) => line.part_type === 'standard')
  expect(standards).toHaveLength(81)

  await page.goto(`/erp/bom?project=${project.id}`)
  const panel = page.getByRole('region', { name: 'BOM 缺料需求', exact: true })
  await panel.getByRole('radio', { name: '采购缺料', exact: true }).check()
  await panel.getByLabel('每页显示条目', { exact: true }).selectOption('10')
  await panel.getByLabel('筛选类别', { exact: true }).selectOption('standard')
  await expect(panel.getByRole('status', { name: 'BOM导出范围' })).toContainText('当前筛选 81 项')
  await panel.getByRole('button', { name: '全选筛选结果', exact: true }).click()
  await expect(panel.getByRole('button', { name: '导出BOM', exact: true })).toContainText('已选 81 项')
  await expect(panel.locator('tbody tr')).toHaveCount(10)
  const radio = panel.getByRole('radio', { name: '采购缺料', exact: true })
  expect(await radio.evaluate(el => el.getBoundingClientRect().width)).toBeLessThan(25)

  async function download(label: string, name: string) {
    await panel.getByRole('button', { name: '导出BOM', exact: true }).click()
    const pending = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: label, exact: true }).click()
    const file = await pending
    await file.saveAs(info.outputPath(name))
    return info.outputPath(name)
  }
  const csvPath = await download('已选 81 项 · CSV', 'selected-81.csv')
  const csv = (await readFile(csvPath, 'utf8')).replace(/^\uFEFF/, '').trim().split(/\r?\n/)
  const headings = csv[0]!.split(',')
  const records = csv.slice(1).map(row => Object.fromEntries(row.split(',').map((value, i) => [headings[i]!, value])))
  expect(records).toHaveLength(81)
  expect(records.every(row => row['物料类别'] === '标准件')).toBe(true)
  expect(records.filter(row => row['物料编码'] === `00${suffix}-0`).map(row => row['单元']).sort()).toEqual(['上料单元', '检测单元'])
  expect(headings).toContain('变更说明')
  for (const field of ['can_edit_bom', 'change_note', '物料ID', '记录ID', '项目ID']) expect(headings).not.toContain(field)
  const xlsxPath = await download('已选 81 项 · Excel', 'selected-81.xlsx')
  // Python is part of the project test runtime; only standard-library ZIP/XML readers are needed here.
  const sheet: string[][] = JSON.parse(execFileSync('python3', ['-c', `import json,sys,zipfile,xml.etree.ElementTree as E
with zipfile.ZipFile(sys.argv[1]) as z:
 root=E.fromstring(z.read('xl/worksheets/sheet1.xml'))
 ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 print(json.dumps([[ ''.join(c.itertext()) for c in r ] for r in root.findall('s:sheetData/s:row',ns)]))`, xlsxPath], { encoding: 'utf8' }))
  expect(sheet).toHaveLength(82)
  expect(sheet[0]).toEqual(headings)
  expect(sheet.slice(1).every(row => row[9] === '标准件' && row[12] === '2.5')).toBe(true)
  await page.screenshot({ path: info.outputPath('selected-export.png'), fullPage: true, animations: 'disabled' })

  const firstSelection = panel.getByRole('checkbox', { name: `选择 00${suffix}-0 上料单元`, exact: true })
  await firstSelection.uncheck()
  const partial = await download('已选 80 项 · CSV', 'selected-80.csv')
  const partialRows = (await readFile(partial, 'utf8')).trim().split(/\r?\n/).slice(1)
  expect(partialRows).toHaveLength(80)
  expect(partialRows.filter(row => row.split(',')[2] === `00${suffix}-0`).map(row => row.split(',')[10])).toEqual(['检测单元'])
  await firstSelection.check()

  // A category switch retains deliberate purchase selections, but exporting the filter must exclude them.
  await panel.getByLabel('筛选类别', { exact: true }).selectOption('custom')
  await expect(panel.getByRole('status', { name: 'BOM导出范围' })).toContainText('81 项在当前筛选外')
  const custom = await download('筛选结果 3 项 · CSV', 'filtered-custom.csv')
  const customRows = (await readFile(custom, 'utf8')).trim().split(/\r?\n/).slice(1)
  expect(customRows).toHaveLength(3)
  expect(customRows.every(row => row.split(',')[9] === '非标件')).toBe(true)
  await panel.getByRole('button', { name: '清空选择', exact: true }).click()
  await panel.getByLabel('筛选类别', { exact: true }).selectOption('standard')
  await panel.getByLabel('筛选品牌', { exact: true }).selectOption('标准品牌')
  await panel.getByLabel('筛选单元', { exact: true }).selectOption('检测单元')
  await panel.getByLabel('搜索 BOM 物料', { exact: true }).fill(`00${suffix}-0`)
  const subset = await download('筛选结果 1 项 · CSV', 'filtered-unit.csv')
  const subsetRows = (await readFile(subset, 'utf8')).trim().split(/\r?\n/).slice(1)
  expect(subsetRows).toHaveLength(1)
  expect(subsetRows[0]!.split(',')[10]).toBe('检测单元')
  await panel.getByLabel('搜索 BOM 物料', { exact: true }).fill('不存在的物料')
  await expect(panel.getByRole('button', { name: '导出BOM', exact: true })).toBeDisabled()
})
