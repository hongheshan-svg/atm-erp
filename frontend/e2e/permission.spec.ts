import { test, expect } from '@playwright/test'

test.describe('Permission Control', () => {
  test('admin user sees full navigation', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')
    await page.waitForURL(/\/(erp\/)?(?!login)/)

    // Admin should see main navigation sections
    const nav = page.locator('.el-menu, nav, [class*="sidebar"]')
    await expect(nav).toBeVisible({ timeout: 10000 })

    // Check core modules are visible
    const menuText = await nav.textContent()
    expect(menuText).toBeTruthy()
  })

  test('dashboard is accessible after login', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')
    await page.waitForURL(/\/(erp\/)?(?!login)/)

    // Should land on dashboard or home
    await expect(page.locator('[class*="dashboard"], [class*="home"], .el-card')).toBeVisible({ timeout: 10000 })
  })

  test('protected routes redirect when not authenticated', async ({ page }) => {
    await page.evaluate(() => localStorage.clear())

    const protectedRoutes = [
      '/erp/sales/orders',
      '/erp/purchase/orders',
      '/erp/inventory',
      '/erp/finance',
    ]

    for (const route of protectedRoutes) {
      await page.goto(route)
      await page.waitForURL(/\/login/, { timeout: 5000 })
      expect(page.url()).toContain('/login')
    }
  })
})
