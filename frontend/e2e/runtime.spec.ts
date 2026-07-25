import { expect, test } from '@playwright/test'
import { loginAsAdmin } from './helpers'

test('dashboard renders without browser runtime errors', async ({ page }) => {
  const runtimeErrors: string[] = []

  page.on('console', message => {
    if (message.type() === 'error' || message.type() === 'warning') {
      runtimeErrors.push(`${message.type()}: ${message.text()}`)
    }
  })
  page.on('pageerror', error => {
    runtimeErrors.push(`pageerror: ${error.message}`)
  })

  await loginAsAdmin(page)
  await expect(page.locator('.dashboard')).toBeVisible()
  expect(runtimeErrors).toEqual([])
})
