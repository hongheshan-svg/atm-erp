import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('login page is accessible', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('form')).toBeVisible()
  })

  test('login with valid credentials', async ({ page }) => {
    await page.goto('/login')

    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')

    await page.waitForURL(/\/(erp\/)?(?!login)/)
    expect(page.url()).not.toContain('/login')
  })

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/login')

    await page.fill('input[type="text"], input[placeholder*="用户"]', 'wrong')
    await page.fill('input[type="password"]', 'wrong')
    await page.click('button[type="submit"], button:has-text("登录")')

    await expect(page.locator('.el-message--error, .el-message')).toBeVisible({ timeout: 5000 })
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.context().clearCookies()
    await page.evaluate(() => localStorage.clear())

    await page.goto('/dashboard')

    await page.waitForURL(/\/login/)
    expect(page.url()).toContain('/login')
  })

  test('logout clears session', async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.fill('input[type="text"], input[placeholder*="用户"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"], button:has-text("登录")')
    await page.waitForURL(/\/(erp\/)?(?!login)/)

    // Trigger logout
    await page.click('.el-dropdown, [class*="avatar"], [class*="user"]')
    await page.click('text=退出, text=登出, text=注销')

    await page.waitForURL(/\/login/)
    expect(page.url()).toContain('/login')
  })
})
