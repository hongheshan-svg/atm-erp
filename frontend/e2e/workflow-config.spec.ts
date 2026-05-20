import { test, expect } from '@playwright/test'

test.describe('Workflow Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')
    await page.waitForURL(/\/(erp\/)?(?!login)/)
  })

  test('navigate to workflow config page', async ({ page }) => {
    await page.goto('/erp/workflow/config')
    await expect(page.locator('.el-table, [class*="workflow"]')).toBeVisible({ timeout: 10000 })
  })

  test('workflow config shows business types', async ({ page }) => {
    await page.goto('/erp/workflow/config')
    await page.waitForSelector('.el-table', { timeout: 10000 })

    // Should have the business type column
    await expect(page.locator('.el-table th:has-text("业务类型"), .el-table th:has-text("类型")')).toBeVisible()
  })

  test('can open create workflow dialog', async ({ page }) => {
    await page.goto('/erp/workflow/config')

    const createBtn = page.locator('button:has-text("新建"), button:has-text("创建"), button:has-text("新增")')
    if (await createBtn.isVisible()) {
      await createBtn.click()
      await expect(page.locator('.el-dialog, .el-drawer')).toBeVisible({ timeout: 5000 })
    }
  })

  test('workflow form has business type selector', async ({ page }) => {
    await page.goto('/erp/workflow/config')

    const createBtn = page.locator('button:has-text("新建"), button:has-text("创建"), button:has-text("新增")')
    if (await createBtn.isVisible()) {
      await createBtn.click()
      await page.waitForSelector('.el-dialog, .el-drawer', { timeout: 5000 })

      const typeSelect = page.locator('.el-select, [class*="business-type"]').first()
      await expect(typeSelect).toBeVisible()
    }
  })
})
