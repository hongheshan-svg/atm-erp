import { test, expect } from './fixtures'
test('登录表单不提交空凭据', async ({ page }) => {
  await page.goto('/erp/login')
  await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/login/)
  await expect(page.getByLabel('用户名')).toBeFocused()
})

// The decorative column used to size the page, so common laptop windows needed scrolling to reach 登录.
test('登录页在常见窗口尺寸下完整显示，不需要滚动', async ({ page }, info) => {
  const sizes = info.project.name === 'mobile' ? [[360, 640], [390, 844]] : [[1280, 720], [1440, 900]]
  await page.goto('/erp/login')
  await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width: width!, height: height! })
    // Resizing reflows asynchronously, so poll instead of sampling the document once.
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollHeight - document.documentElement.clientHeight),
        { message: `${width}x${height} 不应需要纵向滚动` })
      .toBeLessThanOrEqual(1)
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
        { message: `${width}x${height} 不应出现横向滚动` })
      .toBeLessThanOrEqual(1)
    await expect(page.getByRole('button', { name: '登录', exact: true })).toBeInViewport()
    // A shrinking input must not shrink past a usable touch target.
    const inputHeight = await page.getByLabel('密码', { exact: true }).evaluate(el => el.getBoundingClientRect().height)
    expect(inputHeight, `${width}x${height} 密码输入框应保持可点击高度`).toBeGreaterThanOrEqual(44)
  }
})
