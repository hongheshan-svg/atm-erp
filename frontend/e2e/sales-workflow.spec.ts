import { test, expect } from '@playwright/test'

test.describe('Sales Order Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')
    await page.waitForURL(/\/(erp\/)?(?!login)/)
  })

  test('navigate to sales order list', async ({ page }) => {
    await page.goto('/erp/sales/orders')
    await expect(page.locator('.el-table, [class*="order"]')).toBeVisible({ timeout: 10000 })
  })

  test('create new sales order', async ({ page }) => {
    await page.goto('/erp/sales/orders')

    await page.click('button:has-text("新建"), button:has-text("创建"), button:has-text("新增")')
    await page.waitForSelector('.el-dialog, .el-drawer, [class*="form"]', { timeout: 5000 })

    // Fill minimum required fields
    const customerInput = page.locator('[class*="customer"] input, [placeholder*="客户"]').first()
    if (await customerInput.isVisible()) {
      await customerInput.click()
      // Select first option from dropdown
      await page.locator('.el-select-dropdown__item, .el-option').first().click()
    }

    // Verify form is present
    await expect(page.locator('form, .el-form')).toBeVisible()
  })

  test('sales order list shows status column', async ({ page }) => {
    await page.goto('/erp/sales/orders')
    await page.waitForSelector('.el-table', { timeout: 10000 })

    const statusColumn = page.locator('.el-table th:has-text("状态")')
    await expect(statusColumn).toBeVisible()
  })
})
