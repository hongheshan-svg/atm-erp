import { expect, test } from '@playwright/test'

test('容器 OTA 下载、等待重启、确认和重连展示一致', async ({ page }, info) => {
  let status = ''
  let disconnected = false
  let restored = false
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-ui-fixture'))
  await page.route(`${new URL(process.env.E2E_BASE_URL!).origin}/api/**`, async route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'POST') {
      if (path === '/api/core/upgrade/') {
        expect(route.request().postDataJSON()).toEqual({ target: 'v1.8.9', confirmed: true })
        status = 'ready'
      } else {
        expect(path).toBe('/api/core/upgrade/restart/')
        expect(route.request().postDataJSON()).toEqual({ id: 7, confirmed: true })
        status = 'restarting'
      }
      await route.fulfill({ json: { id: 7, target: 'v1.8.9', status, need_restart: status === 'ready' } })
      return
    }
    expect(route.request().method()).toBe('GET')
    if (path === '/api/core/upgrade/' && disconnected) { await route.abort(); return }
    await route.fulfill({ json: path === '/api/auth/me/' ? { id: 1, role: 'admin', username: '隔离界面测试' }
      : path === '/api/core/upgrade/' ? {
        current: restored ? '1.8.9' : '1.8.8', configured: true, execution: 'container', available: !restored,
        job: status ? { id: 7, target: 'v1.8.9', status: restored ? 'succeeded' : status, need_restart: status === 'ready' } : null,
        runner: { mode: 'native', platform: 'linux', execution: 'container' },
        release: { version: 'v1.8.9', notes: '容器内程序升级；备份后前向迁移。' },
      } : { results: [], count: 0 } })
  })
  await page.goto('/erp/settings?section=account')
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '菜单', exact: true }).click()
  await page.locator('.system-upgrade-entry').click()
  const dialog = page.getByRole('dialog', { name: 'ERP 版本与升级' })
  await expect(dialog).toContainText('容器内升级已就绪')
  await expect(dialog).not.toContainText('网页一键升级未启用')
  await expect(dialog).not.toContainText('宿主机升级执行器未连接')
  const submit = dialog.getByRole('button', { name: '立即更新', exact: true })
  await expect(submit).toBeEnabled()
  await expect(dialog.getByRole('checkbox')).toHaveCount(0)
  await submit.click()
  await expect(dialog.getByRole('region', { name: '等待重启' })).toBeVisible()
  const restart = dialog.getByRole('button', { name: '重启服务', exact: true })
  await expect(restart).toBeDisabled()
  await page.screenshot({ path: info.outputPath('container-ota-ready.png'), animations: 'disabled' })
  await dialog.locator('.el-checkbox').click()
  await expect(dialog.getByRole('checkbox')).toBeChecked()
  await expect(restart).toBeEnabled()
  await restart.click()
  await expect(dialog).toContainText('重启生效中')
  disconnected = true
  await expect(dialog).toContainText('正在重新连接', { timeout: 10000 })
  await expect(dialog.getByRole('region', { name: '升级成功' })).toHaveCount(0)
  disconnected = false
  restored = true
  await expect(dialog.getByRole('region', { name: '升级成功' })).toBeVisible({ timeout: 10000 })
  await expect(dialog).toContainText('秒后自动刷新页面')
  await page.screenshot({ path: info.outputPath('container-ota-success.png'), animations: 'disabled' })
  await page.waitForEvent('load', { timeout: 15000 })
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '菜单', exact: true }).click()
  await expect(page.locator('.system-upgrade-entry')).toContainText('v1.8.9')
})

// UI-state tests: all API calls are intercepted; no real upgrade or business write.
test('升级界面：版本说明、失败重试、历史记录与移动端布局', async ({ page }, info) => {
  let checkFailed = false
  const release = { version: 'v1.8.9', notes: '升级模块改进\n保留备份及版本校验。', published_at: '2026-09-20T08:00:00Z', url: 'https://github.com/hongheshan-svg/atm-erp/releases/tag/v1.8.9' }
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-ui-fixture'))
  await page.route(`${new URL(process.env.E2E_BASE_URL!).origin}/api/**`, async route => {
    const url = new URL(route.request().url())
    if (route.request().method() !== 'GET') throw new Error('本用例不允许写入')
    const data = url.pathname === '/api/auth/me/' ? { id: 1, role: 'admin', username: '隔离界面测试' }
      : url.pathname === '/api/core/upgrade/' ? {
        current: '1.8.8', configured: false, runner: null,
        job: { status: 'failed', target: 'v1.8.7', detail: '历史失败原始记录' },
        ...(url.searchParams.has('check') ? { release, available: !checkFailed, cached: checkFailed, checked_at: 1789891200, ...(checkFailed ? { check_error: '网络检查失败，请重试' } : {}) } : {}),
      } : { results: [], count: 0 }
    await route.fulfill({ json: data })
  })
  await page.goto('/erp/settings?section=account')
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '菜单', exact: true }).click()
  await page.locator('.system-upgrade-entry').click()
  const dialog = page.getByRole('dialog', { name: 'ERP 版本与升级' })
  await expect(dialog.getByText('有新版本可升级', { exact: true })).toBeVisible()
  await expect(dialog.getByText('网页一键升级未启用', { exact: true })).toBeVisible()
  await expect(dialog.locator('.upgrade-notes')).toHaveAttribute('open', '')
  await expect(dialog.locator('.upgrade-history')).not.toHaveAttribute('open', '')
  await expect(dialog.getByRole('button', { name: '备份并升级', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: '原生部署', exact: true }).click()
  await expect(dialog.locator('.upgrade-manual')).toContainText('systemd')
  const bounds = await page.locator('.el-dialog.upgrade-dialog').boundingBox()
  expect(bounds!.y).toBeGreaterThanOrEqual(0)
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(page.viewportSize()!.height + 1)
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1)
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
  await dialog.locator('.el-dialog__body').evaluate(el => { el.scrollTop = 0 })
  await page.screenshot({ path: info.outputPath('upgrade-available.png'), animations: 'disabled' })
  checkFailed = true
  await dialog.getByRole('button', { name: '检查新版本', exact: true }).click()
  await expect(dialog.getByText('网络检查失败，请重试', { exact: true })).toBeVisible()
  await expect(dialog).not.toContainText('当前已是最新版本')
  checkFailed = false
  await dialog.getByRole('button', { name: '检查新版本', exact: true }).click()
  await expect(dialog.getByText('有新版本可升级', { exact: true })).toBeVisible()
})
