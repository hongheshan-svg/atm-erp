import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('Permission Control', () => {
  test('admin user sees full navigation', async ({ page }) => {
    await loginAsAdmin(page)

    // Admin should see main navigation sections
    const nav = page.locator('.sidebar')
    await expect(nav).toBeVisible({ timeout: 10000 })

    // Check core modules are visible
    const menuText = await nav.textContent()
    expect(menuText).toBeTruthy()
  })

  test('dashboard is accessible after login', async ({ page }) => {
    await loginAsAdmin(page)

    // Should land on dashboard or home
    await expect(page.locator('.dashboard')).toBeVisible({ timeout: 10000 })
  })

  test('protected routes redirect when not authenticated', async ({ page }) => {
    await page.goto('/erp/login')
    await page.evaluate(() => localStorage.clear())

    const protectedRoutes = [
      '/erp/sales/orders',
      '/erp/purchase/orders',
      '/erp/inventory/stocks',
      '/erp/finance/ar',
    ]

    for (const route of protectedRoutes) {
      await page.goto(route)
      await page.waitForURL(/\/login/, { timeout: 5000 })
      expect(page.url()).toContain('/login')
    }
  })
})
