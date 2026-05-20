import { test, expect } from '@playwright/test'

test.describe('Purchase Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')
    await page.waitForURL(/\/(erp\/)?(?!login)/)
  })

  test('navigate to purchase order list', async ({ page }) => {
    await page.goto('/erp/purchase/orders')
    await expect(page.locator('.el-table, [class*="order"]')).toBeVisible({ timeout: 10000 })
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

    const createBtn = page.locator('button:has-text("新建"), button:has-text("创建"), button:has-text("新增")')
    if (await createBtn.isVisible()) {
      await createBtn.click()
      await expect(page.locator('.el-dialog, .el-drawer, .el-form')).toBeVisible({ timeout: 5000 })
    }
  })

  test('navigate to purchase requests', async ({ page }) => {
    await page.goto('/erp/purchase/requests')
    await expect(page.locator('.el-table, [class*="request"]')).toBeVisible({ timeout: 10000 })
  })
})
