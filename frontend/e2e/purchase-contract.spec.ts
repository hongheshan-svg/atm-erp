import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs'
import { test, expect, login } from './fixtures'

test('完整合同同页显示32行明细和行业条款，PDF自动分页且无遗漏', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}` }, suffix = String(Date.now())
  async function post(path: string, data: object) {
    const response = await page.request.post('/api/business/' + path, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
    expect(response.status(), await response.text()).toBeLessThan(300)
    return response.json()
  }
  const me = await (await page.request.get('/api/auth/me/', { headers })).json()
  const address = '隔离验收供应商地址，车间与收货楼层须完整保留。'.repeat(5)
  const partner = await post('partners/', { name: `非标自动化合同验收单位${suffix}`, kind: 'both', address, phone: '000-12345', contact: '验收联系人' })
  const project = await post('projects/', { name: `非标自动化装配线合同验收${suffix}`, customer: partner.id, manager: me.id })
  const lines = [], codes: string[] = []
  for (let i = 1; i <= 32; i++) {
    const code = `CT-${suffix}-${i}`
    codes.push(code)
    const item = await post('items/', { code, name: `非标零件${i}`, specification: '铝合金加工件，尺寸与表面处理按确认图纸执行。'.repeat(3), drawing_number: `CT-DRAW-${suffix}-${i}`, drawing_revision: 'B', unit: '件', brand: '约定品牌' })
    lines.push({ item: item.id, quantity: '1', unit_price: '10' })
  }
  const note = '补充要求：验收按双方确认图纸执行，资料须随货交付。\n'.repeat(12)
  const purchase = await post('purchases/', { project: project.id, supplier: partner.id, due_date: '2026-12-31', payment_term: 'month30', note, lines })
  await page.goto(`/erp/purchases/${purchase.id}/contract`)
  const contract = page.getByRole('article', { name: '采购合同预览', exact: true })
  await expect(contract).toHaveCount(1)
  await expect(contract.locator('tbody tr')).toHaveCount(32)
  await expect(contract).toContainText(address)
  await expect(contract.locator('.contract-note')).toHaveText(note)
  for (const text of ['32 项物料', '技术要求与图纸版本', '非标自动化配套与变更', '形位公差', '参数备份', '质量、验收与12个月质保', '验收合格之日起12个月', '月结30天', '甲方签字', '乙方签字']) await expect(contract).toContainText(text)
  for (const name of ['查看完整附件', '查看合同正文']) await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  await expect(page.getByRole('checkbox')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  expect(await page.getByLabel('合同版本', { exact: true }).evaluate(el => el.getBoundingClientRect().right <= el.closest('aside')!.getBoundingClientRect().right)).toBe(true)
  const numericColumnsStayOnOneLine = await contract.locator('tbody tr td:first-child, tbody tr td:nth-child(n+5)').evaluateAll(cells => cells.every(cell => {
    const range = document.createRange()
    range.selectNodeContents(cell)
    return range.getClientRects().length === 1
  }))
  expect(numericColumnsStayOnOneLine).toBe(true)
  await page.screenshot({ path: info.outputPath('contract-full.png'), animations: 'disabled', fullPage: true })
  await contract.getByRole('heading', { name: '二、技术要求与图纸版本', exact: true }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('contract-terms.png'), animations: 'disabled' })
  await page.evaluate(() => { window.print = () => { document.body.dataset.printRequested = 'yes' } })
  await page.getByRole('button', { name: '打印 / 另存为 PDF', exact: true }).click()
  await expect(page.locator('body')).toHaveAttribute('data-print-requested', 'yes')
  await page.emulateMedia({ media: 'print' })
  await expect(page.locator('.contract-toolbar:visible')).toHaveCount(0)
  expect(await contract.locator('table').evaluate(el => el.getBoundingClientRect().width <= el.parentElement!.getBoundingClientRect().width + 1)).toBe(true)
  const bytes = await page.pdf({ path: info.outputPath('complete-contract.pdf'), preferCSSPageSize: true, printBackground: true })
  const loadingTask = getDocument({ data: new Uint8Array(bytes), useSystemFonts: true })
  const pdf = await loadingTask.promise
  try {
    expect(pdf.numPages).toBeGreaterThan(1)
    const texts: string[] = []
    for (let i = 1; i <= pdf.numPages; i++) {
      const parsed = await pdf.getPage(i)
      const content = await parsed.getTextContent()
      // Embedded CJK fonts may expose compatibility radicals; compare their normalized text.
      const text = content.items.map(item => 'str' in item ? item.str : '').join('').normalize('NFKC').replace(/\s+/g, '')
      expect(text.length, `第${i}页不能是空白页`).toBeGreaterThan(10)
      texts.push(text)
    }
    const full = texts.join('')
    for (const code of codes) expect(full).toContain(code)
    for (const text of ['技术要求与图纸版本', '形位公差', '非标自动化配套与变更', '参数备份', '违约责任与其他约定', '质量、验收与12个月质保', '验收合格之日起12个月', '补充要求', '甲方签字', '乙方签字', '320.00']) expect(full).toContain(text)
    expect(full).not.toContain('打印/另存为PDF')
    expect(full).not.toContain('最新归档')
  } finally { await loadingTask.destroy() }
  await page.emulateMedia({ media: 'screen' })
})
