import { test, expect } from './fixtures'

test('各入口可直接操作，长表单在短视口保留保存和取消', async ({ page }, info) => {
  await page.goto('/erp/login')
  await page.getByLabel('用户名', { exact: true }).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/workbench/)
  const nav = page.getByRole('navigation', { name: '主导航' })
  for (const name of ['工作台', '销售', '项目', 'BOM', '采购', '库存', '收付款', '基础资料', '设置']) {
    const link = nav.getByRole('link', { name, exact: true })
    await expect(link).toBeInViewport({ ratio: 1 })
    if (info.project.name === 'mobile') await link.tap()
    else await link.click()
    await expect(page.getByRole('heading', { name, exact: true }).first()).toBeVisible()
  }
  await nav.getByRole('link', { name: '项目', exact: true }).click()
  await page.getByRole('button', { name: '新建项目', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const cancel = dialog.getByRole('button', { name: '取消', exact: true })
  const save = dialog.getByRole('button', { name: '保存', exact: true })
  if (info.project.name === 'mobile') {
    await page.setViewportSize({ width: 390, height: 480 })
    await expect(save).toBeInViewport({ ratio: 1 })
    await expect(cancel).toBeInViewport({ ratio: 1 })
    await dialog.getByLabel('质保月数', { exact: true }).fill('12')
    await expect(save).toBeInViewport({ ratio: 1 })
    await page.screenshot({ path: info.outputPath('short-viewport-dialog.png'), animations: 'disabled' })
  }
  if (info.project.name === 'mobile') await cancel.tap()
  else await cancel.click()
  await expect(dialog).not.toBeVisible()
})
