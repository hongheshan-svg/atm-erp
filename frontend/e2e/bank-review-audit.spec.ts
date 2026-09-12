import { createHash } from 'node:crypto'
import { crc32 } from 'node:zlib'
import { test, expect, login, expectHttpError, type Page } from './fixtures'

// A tiny uncompressed ZIP writer keeps this synthetic one-sheet XLSX fixture
// dependency-free. No production code or real bank document is used.
function xlsx(rows: string[][]) {
  const escape = (value: string) => value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const sheet = rows.map((row, index) => `<row r="${index + 1}">${row.map((value, column) => `<c r="${String.fromCharCode(65 + column)}${index + 1}" t="inlineStr"><is><t>${escape(value)}</t></is></c>`).join('')}</row>`).join('')
  const files: Record<string, string> = {
    '[Content_Types].xml': '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    '_rels/.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    'xl/workbook.xml': '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="合成银行流水" sheetId="1" r:id="rId1"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    'xl/worksheets/sheet1.xml': `<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${sheet}</sheetData></worksheet>`,
  }
  const bodies: Buffer[] = [], directory: Buffer[] = []
  let offset = 0
  for (const [path, content] of Object.entries(files)) {
    const name = Buffer.from(path), data = Buffer.from(content), checksum = crc32(data)
    const local = Buffer.alloc(30)
    local.writeUInt32LE(0x04034b50); local.writeUInt16LE(20, 4)
    local.writeUInt32LE(checksum, 14); local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22)
    local.writeUInt16LE(name.length, 26)
    const entry = Buffer.alloc(46)
    entry.writeUInt32LE(0x02014b50); entry.writeUInt16LE(20, 4); entry.writeUInt16LE(20, 6)
    entry.writeUInt32LE(checksum, 16); entry.writeUInt32LE(data.length, 20); entry.writeUInt32LE(data.length, 24)
    entry.writeUInt16LE(name.length, 28); entry.writeUInt32LE(offset, 42)
    bodies.push(local, name, data)
    directory.push(entry, name)
    offset += local.length + name.length + data.length
  }
  const central = Buffer.concat(directory), end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50); end.writeUInt16LE(Object.keys(files).length, 8); end.writeUInt16LE(Object.keys(files).length, 10)
  end.writeUInt32LE(central.length, 12); end.writeUInt32LE(offset, 16)
  return Buffer.concat([...bodies, central, end])
}

const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, reference: string) => page.locator('.el-table__body tr:visible').filter({ hasText: reference })
async function action(page: Page, reference: string, name: string) {
  await row(page, reference).getByRole('button', { name: '操作 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(dialog(page)).toBeVisible()
}

test('财务原生银行导入缺失户名先核实，保留原凭据且重复导入不记重复款', async ({ page }, info) => {
  test.setTimeout(180000)
  const suffix = String(Date.now()), account = `9900${suffix}`
  const filename = `synthetic-bank-${suffix}.xlsx`, reviewedName = `合成核实客户${suffix}`
  const today = new Date().toISOString().slice(0, 10)
  const sourceRow = ['000000001', '009999000001', `${today} 12:00:00`, '贷', '', '', '合成测试货款', '', '', `业务发生账号:${account}`, '100.00', '', '', '1000.00']
  const buffer = xlsx([
    ['[HISTORYDETAIL]'],
    ['凭证号', '对方账号', '交易时间', '借贷标志', '对方单位', '对方行号', '用途', '摘要', '附言', '回单个性化信息', '转入金额', '转出金额', '支付凭证种类', '余额'],
    sourceRow,
  ])
  await info.attach(filename, { body: buffer, contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const adminToken = await page.evaluate(() => localStorage.getItem('access_token'))
  const adminHeaders = { Authorization: `Bearer ${adminToken}` }
  const financeResponse = await page.request.post('/api/auth/users/', { headers: adminHeaders, data: {
    username: `bankreview_${suffix}`, display_name: `银行验收财务${suffix}`, roles: ['finance'], password: 'Bank-review-audit-2026-only',
  } })
  expect(financeResponse.status(), await financeResponse.text()).toBe(201)
  const finance = await financeResponse.json()
  await login(page, finance.username, 'Bank-review-audit-2026-only')
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }
  async function read(path: string) {
    const response = await page.request.get(`/api/business/${path}`, { headers })
    expect(response.status(), await response.text()).toBe(200)
    return response.json()
  }
  const beforePayments = (await read('payments/')).count
  const beforeMatches = (await read('bank-matches/')).count
  await page.goto('/erp/finance?section=bank')
  async function preview(name: string) {
    await page.getByRole('button', { name: '导入', exact: true }).click()
    const pending = page.waitForResponse(r => r.url().endsWith('/bank-records/import-file/') && r.request().method() === 'POST')
    await dialog(page).locator('input[type=file]').setInputFiles({ name, mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer })
    const response = await pending
    expect(response.status(), await response.text()).toBe(200)
    await expect(dialog(page).getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
    return response.json()
  }
  async function confirm(count: number, skipped: number) {
    const pending = page.waitForResponse(r => r.url().endsWith('/bank-records/import-confirm/') && r.request().method() === 'POST')
    await dialog(page).getByRole('button', { name: '确认导入', exact: true }).click()
    const response = await pending
    expect(response.status(), await response.text()).toBe(200)
    expect(await response.json()).toEqual({ count, skipped })
    await expect(dialog(page).getByRole('status')).toContainText(`成功导入 ${count} 条记录，跳过已导入 ${skipped} 条`)
    await dialog(page).getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog(page)).toHaveCount(0)
  }
  const firstPreview = await preview(filename)
  expect(firstPreview).toMatchObject({ count: 1, can_import: true, errors: [], summary: { income: '100.00', expense: '0.00' } })
  expect(firstPreview.rows[0]).toMatchObject({ status: '待核实户名', needs_review: true })
  await expect(dialog(page).locator('.el-table__body tr')).toContainText('待核实户名')
  expect((await read(`bank-records/?search=${account}`)).count).toBe(0)
  expect((await read('payments/')).count).toBe(beforePayments)
  await confirm(1, 0)
  const bank = (await read(`bank-records/?search=${account}`)).results[0]
  expect(bank).toMatchObject({ amount: '100.00', remaining_amount: '100.00', project: null, needs_review: true, matches: [], returns: [] })
  expect(bank.source).toMatchObject({
    file: filename, file_sha256: createHash('sha256').update(buffer).digest('hex'), row: 3,
    original_reference: '000000001', counterparty: '', counterparty_account: '009999000001',
  })
  expect(bank.source.raw.slice(0, 14)).toEqual(sourceRow)
  await expect(row(page, bank.reference)).toContainText('待核实户名')
  await row(page, bank.reference).getByRole('button', { name: '操作 ▾', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: '核实对方户名', exact: true })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '认领到账', exact: true })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: '匹配已有收付款', exact: true })).toHaveCount(0)
  await page.getByRole('menuitem', { name: '查看银行明细', exact: true }).click()
  await expect(dialog(page)).toBeVisible()
  const source = dialog(page).locator('fieldset').filter({ has: page.locator('legend').filter({ hasText: '原始银行凭据' }) })
  await expect(source).toContainText(filename)
  await expect(source).toContainText('000000001')
  await expect(source).toContainText('原文件未提供')
  await dialog(page).getByRole('button', { name: '关闭', exact: true }).click()
  await action(page, bank.reference, '核实对方户名')
  await dialog(page).getByLabel('核实后的对方户名', { exact: true }).fill('原流水未提供户名（待核实）')
  await dialog(page).getByLabel('原因 / 说明', { exact: true }).fill('占位户名不应通过核实')
  expectHttpError(page, `/api/business/bank-records/${bank.id}/review/`, 409)
  let saving = page.waitForResponse(r => r.url().endsWith(`/bank-records/${bank.id}/review/`) && r.request().method() === 'POST')
  await dialog(page).getByRole('button', { name: '保存', exact: true }).click()
  expect((await saving).status()).toBe(409)
  await expect(dialog(page).locator('.el-alert--error')).toContainText('请填写核实后的实际户名')
  expect((await read(`bank-records/${bank.id}/`)).needs_review).toBe(true)
  await dialog(page).getByLabel('核实后的对方户名', { exact: true }).fill(reviewedName)
  await dialog(page).getByLabel('原因 / 说明', { exact: true }).fill(`合成银行回单核对${suffix}`)
  saving = page.waitForResponse(r => r.url().endsWith(`/bank-records/${bank.id}/review/`) && r.request().method() === 'POST')
  await dialog(page).getByRole('button', { name: '保存', exact: true }).click()
  expect((await saving).status()).toBe(200)
  await expect(dialog(page)).toHaveCount(0)
  const reviewed = await read(`bank-records/${bank.id}/`)
  expect(reviewed).toMatchObject({ needs_review: false, counterparty: reviewedName, remaining_amount: '100.00', project: null, matches: [], returns: [] })
  expect(reviewed.source).toEqual(bank.source)
  await expect(row(page, bank.reference)).toContainText(reviewedName)
  await expect(row(page, bank.reference)).toContainText('待认领 / 匹配')
  await row(page, bank.reference).getByRole('button', { name: '操作 ▾', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: '核实对方户名', exact: true })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: '认领到账', exact: true })).toBeVisible()
  if (info.project.use.isMobile) {
    await page.getByRole('heading', { name: '收付款', exact: true }).tap()
  } else {
    await page.getByRole('menuitem', { name: '认领到账', exact: true }).focus()
    await page.getByRole('menuitem', { name: '认领到账', exact: true }).press('Escape')
  }
  await expect(page.getByRole('menuitem', { name: '认领到账', exact: true })).toHaveCount(0)
  const repeated = await preview(`renamed-${filename}`)
  expect(repeated.rows[0].status).toBe('已导入（跳过）')
  await confirm(0, 1)
  const after = await read(`bank-records/?search=${account}`)
  expect(after.count).toBe(1)
  expect(after.results[0]).toMatchObject({ id: bank.id, counterparty: reviewedName, needs_review: false, remaining_amount: '100.00', project: null, matches: [], returns: [] })
  expect(after.results[0].source).toEqual(bank.source)
  expect((await read('payments/')).count).toBe(beforePayments)
  expect((await read('bank-matches/')).count).toBe(beforeMatches)
  const auditResponse = await page.request.get('/api/core/audit/?page_size=100', { headers: adminHeaders })
  expect(auditResponse.status()).toBe(200)
  expect((await auditResponse.json()).results).toEqual(expect.arrayContaining([
    expect.objectContaining({ actor: finance.id, operation: 'bank.review', resource: `bankrecord:${bank.id}`, detail: { counterparty: reviewedName, reason: `合成银行回单核对${suffix}` } }),
  ]))
  await page.screenshot({ path: info.outputPath('bank-reviewed-without-allocation.png'), animations: 'disabled' })
})
