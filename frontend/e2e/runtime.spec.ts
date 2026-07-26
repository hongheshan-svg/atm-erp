import { expect, test } from './fixtures'
import { loginAsAdmin } from './helpers'

test('dashboard renders without browser runtime errors', async ({ page }) => {
  await loginAsAdmin(page)
  await expect(page.locator('.dashboard')).toBeVisible()
})
