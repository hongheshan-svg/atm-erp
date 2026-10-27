import type { TestInfo } from '@playwright/test'
import { createHash, randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { test, expect, login, openRowAction, type Locator, type Page } from './fixtures'

// Real uploads and authenticated APIs only; the parent prepares the isolated installation.
// Run this file with the existing desktop/mobile projects and explicit E2E_* credentials.
// Fixtures: two visible XLSX sheets (122/2 rows, string/numeric zero-padding), a DOCX
// paragraph/table, a 240x120 PNG, and a two-page PDF with distinct text/colour per page.
const fixturePassword = 'Document-preview-isolated-2026-only'
const business = '/api/business/'
const literalText = '<b>按原文显示 & 不改写</b>'
type Upload = { name: string; mimeType: string; buffer: Buffer }
type DocumentRecord = { id: number; original_name: string; sha256: string; size: number }

function api(page: Page, token: string) {
  const headers = { Authorization: `Bearer ${token}` }
  return {
    headers,
    async get(path: string) {
      const response = await page.request.get(path, { headers })
      expect(response.status(), `${path}: ${await response.text()}`).toBe(200)
      return response.json()
    },
    async post(path: string, data: object) {
      const response = await page.request.post(path, {
        headers: { ...headers, 'Idempotency-Key': randomUUID() }, data,
      })
      expect(response.status(), `${path}: ${await response.text()}`).toBe(201)
      return response.json()
    },
  }
}

async function authenticate(page: Page, username: string, password: string) {
  const response = await page.request.post('/api/auth/login/', { data: { username, password } })
  expect(response.status(), await response.text()).toBe(200)
  return api(page, (await response.json()).access)
}

async function actors(page: Page, info: TestInfo, role: string) {
  const suffix = `${info.project.name}-${randomUUID().slice(0, 8)}`
  const admin = await authenticate(page, process.env.E2E_ADMIN_USERNAME || 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const username = `preview_${role}_${suffix}`
  const person = await admin.post('/api/auth/users/', {
    username, display_name: `附件验收-${role}-${suffix}`, roles: [role], password: fixturePassword,
  })
  expect(person.roles).toEqual([role])
  const outsiderName = `preview_outside_${suffix}`
  const outsiderUser = await admin.post('/api/auth/users/', {
    username: outsiderName, display_name: `未参与项目-${suffix}`, roles: ['member'], password: fixturePassword,
  })
  expect(outsiderUser.roles).toEqual(['member'])
  const actor = await authenticate(page, username, fixturePassword)
  const outsider = await authenticate(page, outsiderName, fixturePassword)
  const partner = await admin.post(business + 'partners/', { name: `附件预览单位-${suffix}`, kind: 'both' })
  return { admin, actor, outsider, person, username, partner, suffix }
}

async function binaryFixture(file: string, mimeType: string, suffix: string): Promise<Upload> {
  return {
    name: `${suffix}-${file}`, mimeType,
    buffer: await readFile(new URL(`./fixtures/document-preview/${file}`, import.meta.url)),
  }
}

async function upload(page: Page, client: ReturnType<typeof api>, owner: object, file: Upload): Promise<DocumentRecord> {
  const response = await page.request.post(business + 'documents/', {
    headers: { ...client.headers, 'Idempotency-Key': randomUUID() },
    multipart: { ...owner, category: 'other', file },
  })
  expect(response.status(), await response.text()).toBe(201)
  const created = await response.json()
  const document = await client.get(business + `documents/${created.id}/`)
  expect(document).toMatchObject({
    original_name: file.name, size: file.buffer.length,
    sha256: createHash('sha256').update(file.buffer).digest('hex'),
  })
  return document
}

async function previewRequest(page: Page, id: number, action: () => Promise<unknown>) {
  const pending = page.waitForResponse(response =>
    new URL(response.url()).pathname === business + `documents/${id}/preview/` && response.request().method() === 'GET',
  )
  await action()
  const response = await pending
  expect(response.status(), await response.text()).toBe(200)
  expect(response.request().headers()['authorization']).toMatch(/^Bearer \S+/)
  expect(response.headers()['cache-control']).toContain('no-store')
  return response.json()
}

function viewer(page: Page, name: string) {
  return page.getByRole('dialog', { name: `附件预览 · ${name}`, exact: true })
}

async function screenshot(page: Page, dialog: Locator, info: TestInfo, label: string) {
  await expect(dialog).toBeVisible()
  const viewport = page.viewportSize()!
  // Element Plus animates the overlay's position on entry; retry geometry without scrolling.
  await expect(async () => {
    const bounds = await dialog.boundingBox()
    expect(bounds).not.toBeNull()
    expect(bounds!.x).toBeGreaterThanOrEqual(-1)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width + 1)
    expect(bounds!.y).toBeGreaterThanOrEqual(-1)
    expect(bounds!.height, '整个预览窗口高度不得超过视口').toBeLessThanOrEqual(viewport.height + 1)
    expect(bounds!.y + bounds!.height, '预览窗口底部必须位于视口内').toBeLessThanOrEqual(viewport.height + 1)
  }).toPass({ timeout: 5000 })
  // Assert before any action could auto-scroll the footer into view.
  await expect(dialog.getByRole('button', { name: '关闭预览', exact: true })).toBeInViewport({ ratio: 1 })
  const path = info.outputPath(`${info.project.name}-${label}.png`)
  await page.screenshot({ path, animations: 'disabled' })
  await info.attach(label, { path, contentType: 'image/png' })
}

async function downloadOriginal(page: Page, dialog: Locator, info: TestInfo, file: Upload) {
  const pending = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '下载原文件', exact: true }).click()
  const download = await pending
  expect(download.suggestedFilename()).toBe(file.name)
  const path = info.outputPath(file.name)
  await download.saveAs(path)
  expect(await download.failure()).toBeNull()
  expect((await readFile(path)).equals(file.buffer), '预览后的下载必须逐字节保留原文件').toBe(true)
}

async function deniedPreview(page: Page, outsider: ReturnType<typeof api>, id: number, binary = false) {
  for (const action of binary ? ['preview', 'preview-file', 'download'] : ['preview', 'download']) {
    const path = business + `documents/${id}/${action}/`
    for (const headers of [outsider.headers, {}]) {
      const response = await page.request.get(path, { headers })
      expect([403, 404], `${action} 不应向未参与成员或匿名请求暴露附件`).toContain(response.status())
      expect(response.headers()['content-type']).toContain('application/json')
    }
  }
}

for (const owner of ['purchase', 'sale'] as const) {
  const label = owner === 'purchase' ? '采购' : '销售'
  test(`${label}员工从附件弹窗预览真实XLSX，切表分页保留前导零与原文`, async ({ page }, info) => {
    const f = await actors(page, info, owner === 'purchase' ? 'purchaser' : 'sales_manager')
    let record: { id: number; code: string }
    if (owner === 'purchase') {
      const me = await f.admin.get('/api/auth/me/')
      const project = await f.admin.post(business + 'projects/', {
        name: `采购附件项目-${f.suffix}`, customer: f.partner.id, manager: me.id,
      })
      const item = await f.admin.post(business + 'items/', { name: `预览物料-${f.suffix}`, unit: '件' })
      record = await f.actor.post(business + 'purchases/', {
        project: project.id, supplier: f.partner.id, payment_term: 'month30',
        due_date: new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10),
        lines: [{ item: item.id, quantity: '1', unit_price: '12.50' }],
      })
    } else {
      record = await f.actor.post(business + 'sales/', {
        name: `销售附件-${f.suffix}`, customer: f.partner.id, manager: f.person.id,
      })
    }
    // Business writes return an ID receipt; read the persisted order for its generated code.
    record = await f.actor.get(business + `${owner === 'purchase' ? 'purchases' : 'sales'}/${record.id}/`)
    expect(record.code).toBeTruthy()
    const file = await binaryFixture('two-sheets.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', f.suffix)
    const document = await upload(page, f.actor, { [owner]: String(record.id) }, file)
    await deniedPreview(page, f.outsider, document.id)

    await login(page, f.username, fixturePassword)
    await page.goto(`/erp/${owner === 'purchase' ? 'purchases' : 'sales'}`)
    const search = page.getByRole('searchbox', { name: `搜索${label}订单`, exact: true })
    await search.fill(record.code)
    await search.press('Enter')
    const ownRow = page.locator('.el-table__body tr:visible').filter({ hasText: record.code })
    await expect(ownRow).toHaveCount(1)
    await openRowAction(page, ownRow, '附件')
    const attachments = page.getByRole('dialog', { name: `${label}附件 · ${record.code}`, exact: true })
    const attachmentRow = attachments.locator('.el-table__body tr:visible').filter({ hasText: file.name })
    await expect(attachmentRow).toHaveCount(1)
    const entry = attachmentRow.getByRole('button', { name: owner === 'purchase' ? '预览' : file.name, exact: true })
    const initial = await previewRequest(page, document.id, () => entry.click())
    expect(initial).toMatchObject({ kind: 'spreadsheet', page: 1, total_pages: 2, total_rows: 122 })
    expect(initial.sheets.map((sheet: { name: string }) => sheet.name)).toEqual(['采购明细', '补充说明'])

    const dialog = viewer(page, file.name)
    const table = dialog.getByRole('table', { name: '附件表格', exact: true })
    await expect(table.getByRole('row')).toHaveCount(101) // 100 source rows plus the column headings.
    await expect(dialog).toContainText('第 1 / 2 页')
    await expect(table.getByRole('cell', { name: '000001', exact: true })).toBeVisible()
    const first = table.getByRole('row').filter({ has: page.getByRole('cell', { name: '测试物料-001', exact: true }) })
    await expect(first.getByRole('cell', { name: '000042', exact: true })).toBeVisible() // Numeric 42, format 000000.
    await expect(first.getByRole('cell', { name: literalText, exact: true })).toHaveText(literalText)
    await expect(table.locator('b')).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: '上一页内容', exact: true })).toBeDisabled()
    await screenshot(page, dialog, info, 'spreadsheet')

    const find = dialog.getByRole('searchbox', { name: '查找当前页', exact: true })
    await find.fill('测试物料-001')
    await expect(table.getByRole('row')).toHaveCount(2)
    await find.fill('测试物料-100')
    await expect(dialog).toContainText('本页未找到匹配内容')
    const second = await previewRequest(page, document.id, () => dialog.getByRole('button', { name: '下一页内容', exact: true }).click())
    expect(second).toMatchObject({ page: 2, total_pages: 2, total_rows: 122 })
    await expect(find).toHaveValue('')
    await expect(dialog).toContainText('第 2 / 2 页')
    await expect(table.getByRole('row')).toHaveCount(23)
    await expect(table.getByRole('cell', { name: '测试物料-100', exact: true })).toBeVisible()
    await expect(table.getByRole('cell', { name: '000100', exact: true })).toBeVisible()
    await expect(table.getByRole('cell', { name: '测试物料-121', exact: true })).toHaveCount(1)
    await expect(table.getByRole('cell', { name: '测试物料-001', exact: true })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: '下一页内容', exact: true })).toBeDisabled()
    await screenshot(page, dialog, info, 'spreadsheet-page-2')

    const sheet = dialog.getByRole('combobox', { name: '工作表', exact: true })
    await expect(sheet.locator('option')).toHaveText(['采购明细', '补充说明'])
    const switched = await previewRequest(page, document.id, () => sheet.selectOption({ label: '补充说明' }))
    expect(switched).toMatchObject({ page: 1, total_pages: 1, total_rows: 2 })
    await expect(table.getByRole('cell', { name: '第二张工作表：独立内容', exact: true })).toBeVisible()
    await expect(table.getByRole('cell', { name: '000007', exact: true })).toBeVisible()
    await expect(table.getByRole('row')).toHaveCount(3)
    await previewRequest(page, document.id, () => sheet.selectOption({ label: '采购明细' }))
    await expect(dialog).toContainText('第 1 / 2 页')
    await expect(table.getByRole('cell', { name: '测试物料-001', exact: true })).toBeVisible()
    await downloadOriginal(page, dialog, info, file)
    await dialog.getByRole('button', { name: '关闭预览', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(attachments).toBeVisible()
    await expect(attachmentRow).toContainText(file.name)
  })
}

async function paintedPdf(dialog: Locator, number: number) {
  const canvas = dialog.getByRole('img', { name: `PDF第${number}页`, exact: true })
  await expect(canvas).toBeVisible()
  await expect(dialog.getByRole('region', { name: 'PDF预览', exact: true })).toHaveAttribute('aria-busy', 'false')
  // A canvas element alone also passes for a blank/broken renderer. Check actual pixels.
  const pixels = await canvas.evaluate(element => {
    const target = element as HTMLCanvasElement
    const context = target.getContext('2d')!
    const { data } = context.getImageData(0, 0, target.width, target.height)
    let ink = 0
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3]! > 0 && Math.min(data[i]!, data[i + 1]!, data[i + 2]!) < 220) ink++
    }
    return { width: target.width, height: target.height, ink }
  })
  expect(pixels.width).toBeGreaterThan(100)
  expect(pixels.height).toBeGreaterThan(100)
  expect(pixels.ink).toBeGreaterThan(200)
  return pixels
}

test('项目附件显示PNG、TXT、DOCX及两页PDF，原件下载和未参与成员权限保持', async ({ page }, info) => {
  const f = await actors(page, info, 'manager')
  const project = await f.admin.post(business + 'projects/', {
    name: `多格式附件-${f.suffix}`, customer: f.partner.id, manager: f.person.id,
  })
  const files = [
    { kind: 'image', file: await binaryFixture('drawing.png', 'image/png', f.suffix) },
    { kind: 'text', file: { name: `${f.suffix}-notes.txt`, mimeType: 'text/plain', buffer: Buffer.from(`项目附件正文 000009\n${literalText}\n末行保留。`) } },
    { kind: 'document', file: await binaryFixture('technical-notes.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', f.suffix) },
    { kind: 'pdf', file: await binaryFixture('two-pages.pdf', 'application/pdf', f.suffix) },
  ]
  const documents = []
  for (const sample of files) {
    const document = await upload(page, f.actor, { project: String(project.id) }, sample.file)
    await deniedPreview(page, f.outsider, document.id, ['image', 'pdf'].includes(sample.kind))
    documents.push({ ...sample, document })
  }
  await login(page, f.username, fixturePassword)
  await page.goto(`/erp/projects/${project.id}?tab=documents`)
  await expect(page.getByRole('tab', { name: '附件', exact: true })).toHaveAttribute('aria-selected', 'true')

  for (const { kind, file, document } of documents) {
    const row = page.locator('.el-table__body tr:visible').filter({ hasText: file.name })
    await expect(row).toHaveCount(1)
    const binaryResponse = ['image', 'pdf'].includes(kind) ? page.waitForResponse(response =>
      new URL(response.url()).pathname === business + `documents/${document.id}/preview-file/`,
    ) : undefined
    const result = await previewRequest(page, document.id, () => openRowAction(page, row, '预览附件'))
    expect(result).toMatchObject({ kind, name: file.name })
    if (binaryResponse) {
      const response = await binaryResponse
      expect(response.status()).toBe(200)
      expect(response.headers()['content-type']).toBe(file.mimeType)
      expect(response.headers()['cache-control']).toContain('no-store')
      expect(response.request().headers()['authorization']).toMatch(/^Bearer \S+/)
      expect((await response.body()).equals(file.buffer)).toBe(true)
    }
    const dialog = viewer(page, file.name)
    if (kind === 'image') {
      const image = dialog.getByRole('img', { name: file.name, exact: true })
      await expect(image).toBeVisible()
      await expect.poll(() => image.evaluate(element => {
        const img = element as HTMLImageElement
        return [img.complete, img.naturalWidth, img.naturalHeight]
      })).toEqual([true, 240, 120])
      await screenshot(page, dialog, info, 'preview-image')
    } else if (kind === 'text') {
      await expect(dialog.locator('pre')).toHaveText(file.buffer.toString('utf8'))
      await expect(dialog.locator('pre b')).toHaveCount(0)
    } else if (kind === 'document') {
      await expect(dialog.getByLabel('文档内容', { exact: true })).toContainText('技术说明：DOCX 原文 000008')
      await expect(dialog.getByRole('table', { name: '文档表格', exact: true })).toContainText('端子编号')
      await expect(dialog.getByRole('cell', { name: '000008', exact: true })).toBeVisible()
    } else {
      await paintedPdf(dialog, 1)
      const pages = dialog.getByRole('combobox', { name: 'PDF页码', exact: true })
      await expect(pages.locator('option')).toHaveText(['1', '2'])
      await expect(pages).toHaveValue('1')
      await expect(dialog.getByRole('button', { name: '上一页PDF', exact: true })).toBeDisabled()
      await dialog.getByRole('button', { name: '查看本页文字', exact: true }).click()
      await expect(dialog.locator('pre')).toContainText('Attachment preview - page 1')
      await screenshot(page, dialog, info, 'pdf-page-1')
      await dialog.getByRole('button', { name: '下一页PDF', exact: true }).click()
      const pageTwo = await paintedPdf(dialog, 2)
      await expect(pages).toHaveValue('2')
      await expect(dialog.getByRole('img', { name: 'PDF第1页', exact: true })).toHaveCount(0)
      await expect(dialog.locator('pre')).toContainText('Attachment preview - page 2')
      await expect(dialog.locator('pre')).not.toContainText('Attachment preview - page 1')
      await expect(dialog.getByRole('button', { name: '下一页PDF', exact: true })).toBeDisabled()
      await screenshot(page, dialog, info, 'pdf-page-2')
      await dialog.getByRole('combobox', { name: 'PDF缩放', exact: true }).selectOption('150')
      await expect.poll(async () => dialog.getByRole('img', { name: 'PDF第2页', exact: true })
        .evaluate(element => (element as HTMLCanvasElement).width)).toBeGreaterThan(pageTwo.width * 1.3)
      await paintedPdf(dialog, 2)
      await pages.selectOption('1')
      await paintedPdf(dialog, 1)
      await expect(dialog.locator('pre')).toContainText('Attachment preview - page 1')
    }
    await expect(dialog.getByRole('alert')).toHaveCount(0)
    await downloadOriginal(page, dialog, info, file)
    await dialog.getByRole('button', { name: '关闭预览', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(row).toContainText(file.name)
    expect(await f.actor.get(business + `documents/${document.id}/`)).toMatchObject({
      sha256: document.sha256, size: document.size, original_name: file.name,
    })
  }
})
