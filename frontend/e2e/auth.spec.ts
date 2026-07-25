import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test.describe('Authentication', () => {
  test('login page is accessible', async ({ page }) => {
    await page.goto('/erp/login')
    await expect(page.locator('form')).toBeVisible()
  })

  test('login with valid credentials', async ({ page }) => {
    await loginAsAdmin(page)
    expect(page.url()).not.toContain('/login')
  })

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/erp/login')

    await page.fill('input[type="text"], input[placeholder*="用户"]', 'wrong')
    await page.fill('input[type="password"]', 'wrong')
    await page.click('.login-btn')

    const errorMessage = page.locator('.el-message--error')
    await expect(errorMessage).toHaveCount(1)
    await expect(errorMessage).toContainText('用户名或密码错误')
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/erp/login')
    await page.evaluate(() => localStorage.clear())

    await page.goto('/erp/dashboard')

    await page.waitForURL(/\/login/)
    expect(page.url()).toContain('/login')
  })

  test('logout clears session', async ({ page }) => {
    await loginAsAdmin(page)

    await page.click('.user-block')
    await page.getByText('退出登录', { exact: true }).click()
    await page.locator('.el-message-box').getByRole('button', { name: '确定', exact: true }).click()

    await page.waitForURL(/\/login/)
    expect(page.url()).toContain('/login')
  })
})
