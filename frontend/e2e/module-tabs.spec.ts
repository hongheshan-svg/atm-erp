import { test, expect, login } from './fixtures'

test('分模块页签支持直达、刷新、记忆和无效入口回退', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  for (const [path, first, second, section] of [
    ['masterdata', '物料', '客户与供应商', 'partners'],
    ['inventory', '现有库存', '库存流水', 'moves'],
    ['finance', '应收应付与费用', '收付款流水', 'payments'],
  ]) {
    await page.goto(`/erp/${path}`)
    await expect(page.getByRole('region', { name: first, exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: second, exact: true })).toHaveCount(0)
    await page.getByRole('tab', { name: second, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`section=${section}`))
    await expect(page.getByRole('region', { name: first, exact: true })).not.toBeVisible()
    await expect(page.getByRole('region', { name: second, exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByRole('tab', { name: second, exact: true })).toHaveAttribute('aria-selected', 'true')
    await page.goto(`/erp/${path}?section=unknown`)
    await expect(page).toHaveURL(new RegExp(`section=${section}`))
    await expect(page.getByRole('region', { name: second, exact: true })).toBeVisible()
    await page.screenshot({ path: info.outputPath(`${path}-tabs.png`), fullPage: true, animations: 'disabled' })
  }
  if (info.project.name === 'mobile') {
    await page.goto('/erp/settings?section=users')
    const bar = page.locator('.module-tabs > .el-tabs__header .el-tabs__nav-scroll')
    const box = (await bar.boundingBox())!
    const cdp = await page.context().newCDPSession(page)
    const y = box.y + box.height / 2
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: box.x + box.width - 30, y }] })
    for (let step = 1; step <= 5; step++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: box.x + box.width - 30 - step * 45, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(() => bar.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
    await page.getByRole('tab', { name: '我的账户', exact: true }).click()
    await page.reload()
    await expect(page.getByRole('tab', { name: '我的账户', exact: true })).toBeInViewport()
    await cdp.detach()
  }
})
