import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('Purchase Flow', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('navigate to purchase order list', async ({ page }) => {
    await page.goto('/erp/purchase/orders')
    await expect(page.locator('.purchase-order-list .el-table')).toBeVisible({ timeout: 10000 })
  })

  test('purchase order list has required columns', async ({ page }) => {
    await page.goto('/erp/purchase/orders')
    await page.waitForSelector('.el-table', { timeout: 10000 })

    await expect(page.locator('.el-table th:has-text("订单号")')).toBeVisible()
    await expect(page.locator('.el-table th:has-text("供应商")')).toBeVisible()
    await expect(page.locator('.el-table th:has-text("状态")')).toBeVisible()
  })

  test('can open purchase order creation form', async ({ page }) => {
    await page.goto('/erp/purchase/orders')

    await page.getByRole('button', { name: '创建订单', exact: true }).click()
    await expect(page.locator('.el-dialog')).toBeVisible({ timeout: 5000 })
  })

  test('navigate to purchase requests', async ({ page }) => {
    await page.goto('/erp/purchase/requests')
    await expect(page.locator('.purchase-request-list')).toBeVisible({ timeout: 10000 })
  })
})
