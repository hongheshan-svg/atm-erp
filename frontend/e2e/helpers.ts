import type { Page } from '@playwright/test'

interface AuthState {
  accessToken: string
  refreshToken: string
}

let cachedAuthState: AuthState | null = null

export const loginAsAdmin = async (page: Page) => {
  if (cachedAuthState) {
    await page.goto('/erp/login')
    await page.evaluate(({ accessToken, refreshToken }) => {
      localStorage.setItem('access_token', accessToken)
      localStorage.setItem('refresh_token', refreshToken)
    }, cachedAuthState)
    await page.goto('/erp/dashboard')
    await page.waitForURL(/\/erp\/dashboard/)
    return
  }

  const username = process.env.E2E_USERNAME || 'admin'
  const password = process.env.E2E_PASSWORD

  if (!password) {
    throw new Error('E2E_PASSWORD is required for authenticated browser tests')
  }

  await page.goto('/erp/login')
  await page.fill('input[type="text"], input[placeholder*="用户"]', username)
  await page.fill('input[type="password"]', password)
  await page.click('.login-btn')
  await page.waitForURL(/\/erp\/(?!login)/)

  cachedAuthState = await page.evaluate(() => ({
    accessToken: localStorage.getItem('access_token') || '',
    refreshToken: localStorage.getItem('refresh_token') || '',
  }))

  if (!cachedAuthState.accessToken || !cachedAuthState.refreshToken) {
    cachedAuthState = null
    throw new Error('Login succeeded without storing authentication tokens')
  }
}
