import { expect, type Locator, type Page } from './fixtures'

export async function confirmSettlement(finance: Page, approver: Page, entry: Locator, prepayment = false) {
  const financeUrl = finance.url(), approverUrl = approver.url()
  await entry.getByRole('button', { name: '操作 ▾', exact: true }).click()
  await finance.getByRole('menuitem', { name: prepayment ? '申请预付款核准' : '生成对账单', exact: true }).click()
  let dialog = finance.getByRole('dialog')
  if (prepayment) await dialog.getByLabel('合同编号及付款条款依据', { exact: true }).fill('HT-E2E 合同约定付款额度，经理核准后执行')
  await dialog.getByLabel('原因 / 说明', { exact: true }).fill('核对双方原始业务记录')
  const created = finance.waitForResponse(r => r.url().endsWith('/reconciliations/') && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  const response = await created
  expect(response.status(), await response.text()).toBe(201)
  const statement = await response.json()
  await expect(dialog).not.toBeVisible()
  await approver.goto(`/erp/finance?section=reconciliations&resource=reconciliations&focus=${statement.id}`)
  dialog = approver.getByRole('dialog')
  await expect(dialog.getByRole('button', { name: '确认对账', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '确认对账', exact: true }).click()
  await dialog.getByLabel('原因 / 说明', { exact: true }).fill('确认合同及收退货与资金记录')
  const confirmed = approver.waitForResponse(r => r.url().endsWith(`/reconciliations/${statement.id}/confirm/`) && r.request().method() === 'POST')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  const confirmedResponse = await confirmed
  expect(confirmedResponse.status(), await confirmedResponse.text()).toBe(200)
  await expect(dialog).not.toBeVisible()
  if (approver !== finance) await approver.goto(approverUrl)
  await finance.goto(financeUrl)
  return statement.id as number
}
