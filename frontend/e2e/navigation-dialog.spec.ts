import { test, expect, login } from './fixtures'

test('管理员从左上角查看版本，未连接执行器时不能升级', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '菜单', exact: true }).click()
  const entry = page.getByRole('button', { name: /版本与升级/ })
  await expect(entry).toBeInViewport({ ratio: 1 })
  await entry.click()
  const dialog = page.getByRole('dialog', { name: 'ERP 版本与升级', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('当前版本')
  const bounds = await dialog.boundingBox()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await expect(dialog.getByRole('button', { name: '备份并升级', exact: true })).toBeDisabled()
  await page.screenshot({ path: info.outputPath('system-upgrade.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).not.toBeVisible()
})

test('各入口可直接操作，长表单在短视口保留保存和取消', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const nav = page.getByRole('navigation', { name: '主导航' })
  for (const name of ['工作台', '经营报表', '销售', '项目', 'BOM', '采购', '库存', '收付款', '基础资料', '设置']) {
    if (info.project.name === 'mobile' && !(await nav.isVisible())) await page.getByRole('button', { name: '菜单', exact: true }).click()
    const link = nav.getByRole('link', { name, exact: true })
    await expect(link).toBeInViewport({ ratio: 1 })
    if (info.project.name === 'mobile') await link.tap()
    else await link.click()
    await expect(page.getByRole('heading', { name, exact: true }).first()).toBeVisible()
  }
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '菜单', exact: true }).click()
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
