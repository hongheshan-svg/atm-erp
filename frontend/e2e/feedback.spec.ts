import { test, expect, login, expectHttpError } from './fixtures'

// 测试安装不配置 GitHub 令牌：只验证入口、来源页面带入、详细描述字段、私有仓库提示与令牌格式校验，不向 GitHub 建 issue 或上传附件。
test('问题反馈：从当前页面进入带上路径，未配置连接时不能提交，令牌格式在服务端校验', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  await page.goto('/erp/purchases?resource=purchases&search=不该带上的客户')
  await expect(page.locator('h1')).toBeVisible()
  if (info.project.name === 'mobile' && !(await page.getByRole('link', { name: '反馈问题', exact: true }).isVisible())) {
    await page.goto('/erp/feedback?from=' + encodeURIComponent('/purchases?resource=purchases&search=不该带上的客户'))
  } else {
    await page.getByRole('link', { name: '反馈问题', exact: true }).click()
  }
  await expect(page.getByRole('heading', { name: '问题反馈', exact: true, level: 1 })).toBeVisible()
  await expect(page.getByLabel('相关页面（选填）')).toHaveValue('/purchases?resource=purchases')
  await expect(page.getByText('只有系统维护者能看到')).toBeVisible()
  await expect(page.getByText('尚未配置 GitHub 连接')).toBeVisible()
  await page.getByLabel('标题', { exact: true }).fill('浏览器验收')
  await page.getByLabel('问题描述', { exact: true }).fill('只验证页面，不提交')
  await expect(page.getByRole('button', { name: '提交', exact: true })).toBeDisabled()
  await expect(page.getByLabel('截图与附件（选填）')).toBeDisabled()
  for (const label of ['影响程度（选填）', '出现频率（选填）', '操作步骤（选填）', '期望结果（选填）']) await expect(page.getByLabel(label)).toBeVisible()
  const connection = page.getByRole('region', { name: 'GitHub 连接' })
  await expect(connection).toContainText('atm-erp-feedback')
  await expect(connection).toContainText('未配置')
  await connection.getByLabel('GitHub 令牌', { exact: true }).fill('not-a-github-token')
  expectHttpError(page, '/api/core/feedback/settings/', 400)
  await connection.getByRole('button', { name: '保存', exact: true }).click()
  await expect(connection.getByRole('alert')).toContainText('令牌格式不正确')
  await expect(connection).toContainText('未配置')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true)
  await page.screenshot({ path: info.outputPath('feedback.png'), fullPage: true, animations: 'disabled' })
})
