import { test, expect } from './fixtures'
test('登录表单不提交空凭据', async ({ page }) => {
  await page.goto('/erp/login')
  await expect(page.getByRole('heading', { name: '项目 ERP' })).toBeVisible()
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/login/)
  await expect(page.getByLabel('用户名')).toBeFocused()
})
