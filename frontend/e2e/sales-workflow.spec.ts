import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('Sales Order Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('navigate to sales order list', async ({ page }) => {
    await page.goto('/erp/sales/orders')
    await expect(page.locator('.sales-order-list .el-table')).toBeVisible({ timeout: 10000 })
  })

  test('create new sales order', async ({ page }) => {
    await page.goto('/erp/sales/orders')

    await page.getByRole('button', { name: '创建订单', exact: true }).click()
    await page.waitForSelector('.el-dialog', { timeout: 5000 })

    // Verify form is present
    await expect(page.locator('.el-dialog .el-form')).toBeVisible()
  })

  test('sales order list shows status column', async ({ page }) => {
    await page.goto('/erp/sales/orders')
    await page.waitForSelector('.el-table', { timeout: 10000 })

    const statusColumn = page.locator('.el-table th:has-text("状态")')
    await expect(statusColumn).toBeVisible()
  })
})
