import { randomUUID } from 'node:crypto'
import { test, expect, login, type Page } from './fixtures'

// Real API fixtures: prepare one approved, unreceived purchase; no sales/receiving UI chain.
const fixturePassword = 'Finance-usability-isolated-2026-only'
const paymentAmount = '125.00'
const business = '/api/business/'

function api(page: Page, token: string) {
  const headers = { Authorization: `Bearer ${token}` }
  return {
    headers,
    async get(path: string) {
      const response = await page.request.get(path, { headers })
      expect(response.status(), `${path}: ${await response.text()}`).toBe(200)
      return response.json()
    },
    async post(path: string, data: object, status: number, key: string = randomUUID()) {
      const response = await page.request.post(path, { headers: { ...headers, 'Idempotency-Key': key }, data })
      expect(response.status(), `${path}: ${await response.text()}`).toBe(status)
      return response.json()
    },
  }
}

async function authenticate(page: Page, username: string, password: string) {
  const response = await page.request.post('/api/auth/login/', { data: { username, password } })
  expect(response.status(), await response.text()).toBe(200)
  return api(page, (await response.json()).access)
}

async function fixture(page: Page) {
  const suffix = randomUUID().slice(0, 8)
  const admin = await authenticate(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const me = await admin.get('/api/auth/me/')
  const financeName = `uxfinance_${suffix}`
  const purchaserName = `uxbuyer_${suffix}`
  for (const [username, role] of [[financeName, 'finance'], [purchaserName, 'purchaser']]) {
    const user = await admin.post('/api/auth/users/', {
      username, display_name: `易用性${role}-${suffix}`, roles: [role], password: fixturePassword,
    }, 201)
    expect(user.roles).toEqual([role])
  }
  const finance = await authenticate(page, financeName, fixturePassword)
  const purchaser = await authenticate(page, purchaserName, fixturePassword)
  const partner = await admin.post(business + 'partners/', { name: `付款验收单位-${suffix}`, kind: 'both' }, 201)
  const item = await admin.post(business + 'items/', { name: `付款验收物料-${suffix}`, unit: '件' }, 201)
  const project = await admin.post(business + 'projects/', {
    name: `付款易用性-${suffix}`, customer: partner.id, manager: me.id,
  }, 201)
  const purchase = await admin.post(business + 'purchases/', {
    project: project.id, supplier: partner.id, due_date: '2026-12-31', payment_term: 'month30',
    lines: [{ item: item.id, quantity: '5', unit_price: '100' }],
  }, 201)
  await admin.post(business + `purchases/${purchase.id}/submit/`, {}, 200)
  await admin.post(business + `purchases/${purchase.id}/approve/`, {
    reason: '隔离夹具：管理员记录本人采购申请的例外审批依据',
  }, 200)
  const entries = await admin.get(business + `entries/?project=${project.id}`)
  expect(entries.count).toBe(1)
  const entry = entries.results[0]
  expect(entry.purchase).toBe(purchase.id)
  expect(Number(entry.balance)).toBe(500)
  expect(Number(entry.paid_amount)).toBe(0)
  expect(entry.payment_schedule).toEqual([]) // No receipt batches; cannot settle as ordinary received goods.
  return { admin, finance, purchaser, financeName, project, entry, purchase, suffix }
}

async function openPayment(page: Page, entryId: number) {
  await page.goto(`/erp/finance?section=entries&resource=entries&focus=${entryId}`)
  await page.getByRole('dialog').getByRole('button', { name: '登记收付款', exact: true }).click()
  const form = page.getByRole('dialog', { name: '登记收付款', exact: true })
  await expect(form).toBeVisible()
  return form
}

async function noPayments(f: Awaited<ReturnType<typeof fixture>>) {
  const payments = await f.admin.get(business + `payments/?entry=${f.entry.id}`)
  expect(payments.count).toBe(0)
  const entry = await f.admin.get(business + `entries/${f.entry.id}/`)
  expect(Number(entry.balance)).toBe(500)
  expect(Number(entry.paid_amount)).toBe(0)
}

test('U04 未收货付款先说明前置条件，可就近申请核准并查看真实结果，财务不能自行核准', async ({ page }, info) => {
  const f = await fixture(page)
  await login(page, f.financeName, fixturePassword)
  let form = await openPayment(page, f.entry.id)
  await expect(form.getByRole('status')).toContainText('未收货预付款按合同申请核准')
  await expect(form.locator('button[type="submit"]')).toHaveCount(0)
  await expect(form.getByLabel('金额（元）', { exact: true })).toHaveCount(0)
  await expect(form.getByRole('button', { name: '申请预付款核准', exact: true })).toBeInViewport()
  await page.screenshot({ path: info.outputPath('payment-prerequisites.png'), animations: 'disabled' })
  await form.getByRole('button', { name: '查看已有对账与核准', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/projects/${f.project.id}\\?tab=finance&section=reconciliations`))

  form = await openPayment(page, f.entry.id)
  await form.getByRole('button', { name: '申请预付款核准', exact: true }).click()
  const application = page.getByRole('dialog', { name: '申请预付款核准', exact: true })
  const basis = `合同 UX-${f.suffix}：未收货预付25%，125元`
  await application.getByLabel('本次申请额度（元）', { exact: true }).fill(paymentAmount)
  await application.getByLabel('合同编号及付款条款依据', { exact: true }).fill(basis)
  await application.getByLabel('原因 / 说明', { exact: true }).fill('隔离验收：提交给项目负责人核准')
  const pending = page.waitForResponse(r => r.url().endsWith('/business/reconciliations/') && r.request().method() === 'POST')
  await application.locator('button[type="submit"]').click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(201)
  const saved = await response.json()
  const statement = await f.finance.get(business + `reconciliations/${saved.id}/`)
  expect(statement).toMatchObject({ entry: f.entry.id, project: f.project.id, kind: 'prepayment', status: 'draft', basis, valid: true })
  expect(Number(statement.approved_amount)).toBe(125)
  expect(Number(statement.snapshot.received_net)).toBe(0)
  await f.finance.post(business + `reconciliations/${saved.id}/confirm/`, { reason: '财务不得自行核准预付款' }, 403)
  expect((await f.finance.get(business + `reconciliations/${saved.id}/`)).status).toBe('draft')
  await noPayments(f)
  await info.attach('prepayment-facts', { body: JSON.stringify({ entry: f.entry.id, reconciliation: saved.id, status: statement.status, approved: statement.approved_amount, payments: 0 }), contentType: 'application/json' })

  await expect(application).toBeHidden()
  await expect(page.locator('.saved-result')).toContainText('申请预付款核准成功')
  await page.getByRole('button', { name: '查看结果并继续', exact: true }).click()
  // Compare the actual returned ID: entry and reconciliation are independent sequences.
  await expect(page).toHaveURL(new RegExp(`section=reconciliations&resource=reconciliations&focus=${saved.id}(?:&|$)`))
  const detail = page.getByRole('dialog', { name: '查看对账明细', exact: true })
  await expect(detail).toContainText(basis)
  await expect(detail.getByRole('button', { name: '确认对账', exact: true })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('prepayment-created-result.png'), animations: 'disabled' })
})

test('U14 有效核准后在付款表单上传并选中凭证，实际付款及重试只记一次，采购无资金权限', async ({ page }, info) => {
  const f = await fixture(page)
  const statement = await f.finance.post(business + 'reconciliations/', {
    entry: f.entry.id, kind: 'prepayment', counterparty_balance: '500.00', approved_amount: paymentAmount,
    basis: `合同 UX-${f.suffix}：预付25%`, reason: '隔离夹具：财务申请预付款',
  }, 201)
  await f.admin.post(business + `reconciliations/${statement.id}/confirm/`, { reason: '项目负责人核对合同后核准' }, 200)
  expect(await f.finance.get(business + `reconciliations/${statement.id}/`)).toMatchObject({ status: 'confirmed', valid: true })

  const receipt = { name: `receipt-${f.suffix}.txt`, mimeType: 'text/plain', buffer: Buffer.from(`隔离付款凭证 UX-${f.suffix}，金额125.00元`) }
  const deniedUpload = await page.request.post(business + 'documents/', {
    headers: { ...f.purchaser.headers, 'Idempotency-Key': randomUUID() },
    multipart: { project: String(f.project.id), category: 'receipt', file: receipt },
  })
  expect(deniedUpload.status(), await deniedUpload.text()).toBe(403)
  expect((await f.admin.get(business + `documents/?project=${f.project.id}&category=receipt`)).count).toBe(0)

  await login(page, f.financeName, fixturePassword)
  const form = await openPayment(page, f.entry.id)
  await expect(form.locator('.action-blocker')).toHaveCount(0)
  await expect(form.getByLabel('已确认对账 / 预付款核准', { exact: true })).toHaveValue(String(statement.id))
  await form.getByLabel('金额（元）', { exact: true }).fill(paymentAmount)
  await form.getByLabel('日期', { exact: true }).fill(new Date().toISOString().slice(0, 10))
  await form.getByLabel('原因 / 说明', { exact: true }).fill('隔离验收：按核准登记一次真实预付')
  await form.getByLabel('结算方式', { exact: true }).selectOption('bank')
  await form.getByLabel('账户标识', { exact: true }).fill('隔离测试账户')
  await form.getByLabel('银行流水号', { exact: true }).fill(`UX-${f.suffix}`)
  const uploading = page.waitForResponse(r => r.url().endsWith('/business/documents/') && r.request().method() === 'POST')
  await form.getByLabel('上传结算凭证', { exact: true }).setInputFiles(receipt)
  const uploaded = await uploading
  expect(uploaded.status(), await uploaded.text()).toBe(201)
  const document = await uploaded.json()
  await expect(form.getByLabel('结算凭证', { exact: true })).toHaveValue(String(document.id))
  await expect(form.getByLabel('结算凭证', { exact: true }).locator('option:checked')).toHaveText(receipt.name)
  expect(await f.finance.get(business + `documents/${document.id}/`)).toMatchObject({ project: f.project.id, category: 'receipt', original_name: receipt.name })
  await noPayments(f) // Upload alone must never create a Payment or consume the approval.
  expect(Number((await f.finance.get(business + `reconciliations/${statement.id}/`)).remaining_amount)).toBe(125)
  const submit = form.getByRole('button', { name: '登记收付款记录', exact: true })
  await form.getByLabel('结算凭证', { exact: true }).scrollIntoViewIfNeeded()
  await expect(form.getByLabel('结算凭证', { exact: true })).toBeInViewport()
  await expect(submit).toBeEnabled()
  await expect(submit).toBeInViewport()
  await page.screenshot({ path: info.outputPath('receipt-selected-before-payment.png'), animations: 'disabled' })

  const paying = page.waitForResponse(r => r.url().endsWith(`/entries/${f.entry.id}/pay/`) && r.request().method() === 'POST')
  await submit.click()
  const paid = await paying
  expect(paid.status(), await paid.text()).toBe(200)
  const payment = await paid.json()
  const payload = paid.request().postDataJSON()
  expect(Number(payload.document)).toBe(document.id)
  expect(Number(payload.reconciliation)).toBe(statement.id)
  const key = paid.request().headers()['idempotency-key']
  expect(key).toBeTruthy()
  expect(await f.finance.post(business + `entries/${f.entry.id}/pay/`, payload, 200, key)).toEqual(payment)
  // A new operation cannot reuse the exhausted approval; another role cannot replay it either.
  await f.finance.post(business + `entries/${f.entry.id}/pay/`, payload, 409)
  await f.purchaser.post(business + `entries/${f.entry.id}/pay/`, payload, 403, key)
  const payments = await f.finance.get(business + `payments/?entry=${f.entry.id}`)
  expect(payments.count).toBe(1)
  const stored = payments.results[0]
  expect(stored).toMatchObject({ id: payment.id, document: document.id, reconciliation: statement.id, reference: `UX-${f.suffix}` })
  expect(Number(stored.amount)).toBe(125)
  expect(Number(stored.cash_amount)).toBe(-125)
  expect(stored.evidence).toEqual([{ document: document.id, name: receipt.name, reason: '登记时关联' }])
  const balance = await f.finance.get(business + `entries/${f.entry.id}/`)
  expect(Number(balance.paid_amount)).toBe(125)
  expect(Number(balance.balance)).toBe(375)
  expect(Number((await f.finance.get(business + `reconciliations/${statement.id}/`)).remaining_amount)).toBe(0)
  const doc = await f.finance.get(business + `documents/${document.id}/`)
  const download = await page.request.get(doc.download_url, { headers: f.finance.headers })
  expect(download.status()).toBe(200)
  expect(await download.body()).toEqual(receipt.buffer)
  const deniedDownload = await page.request.get(doc.download_url, { headers: f.purchaser.headers })
  expect(deniedDownload.status()).toBe(404)
  expect((await f.finance.get('/api/auth/me/')).roles).toEqual(['finance'])
  expect((await f.purchaser.get('/api/auth/me/')).roles).toEqual(['purchaser'])
  await info.attach('payment-facts', { body: JSON.stringify({ entry: f.entry.id, reconciliation: statement.id, payment: stored, paid: balance.paid_amount, balance: balance.balance }), contentType: 'application/json' })
  await expect(form).toBeHidden()
  await expect(page.locator('.saved-result')).toContainText('登记收付款成功')
})
