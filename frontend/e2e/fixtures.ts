import { test as base, expect, type Locator, type Page } from '@playwright/test'
import { setTimeout as pause } from 'node:timers/promises'
import { primaryActions } from '../src/row-actions'

const expectedHttpErrors = new WeakMap<Page, { url: string; status: number }[]>()

// 业务日期独立于 CI 主机和浏览器时区；UTC 日期在中国午夜后会落后一天。
export function businessDate(offset = 0) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date(Date.now() + offset * 86400000))
}

export function expectHttpError(page: Page, path: string, status: number) {
  const expected = expectedHttpErrors.get(page) || []
  const rule = { url: new URL(path, page.url()).href, status }
  expected.push(rule)
  expectedHttpErrors.set(page, expected)
  return () => { const index = expected.indexOf(rule); if (index !== -1) expected.splice(index, 1) }
}

export async function login(page: Page, username: string, password: string) {
  await page.goto('/erp/login')
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  for (let attempt = 0; attempt < 3; attempt++) {
    const stopExpecting = expectHttpError(page, '/api/auth/login/', 429)
    const pending = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/login/' && r.request().method() === 'POST')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    const response = await pending
    if (response.status() !== 429) {
      stopExpecting()
      expect(response.status(), await response.text()).toBe(200)
      await expect(page).toHaveURL(/workbench/)
      return
    }
    await expect(page.getByRole('alert')).toContainText('限流')
    const seconds = Number(response.headers()['retry-after'])
    expect(seconds).toBeGreaterThan(0)
    expect(seconds).toBeLessThanOrEqual(60)
    await pause(seconds * 1000 + 200)
    stopExpecting()
  }
  throw new Error('服务器登录限流等待后仍未恢复。')
}

// A row's next step is a direct button and everything else lives in the 操作 menu, so callers
// name the action and let this decide where it currently is.
export async function openRowAction(page: Page, row: Locator, name: string) {
  const menu = row.getByRole('button', { name: '操作 ▾', exact: true })
  // 款项行的主按钮按方向显示「登记收款 / 登记付款」，动作仍是同一个「登记收付款」。
  const direct = name === '登记收付款' ? row.getByRole('button', { name: /^登记(收付款|收款|付款)$/ }) : row.getByRole('button', { name, exact: true })
  await expect(direct.or(menu).first()).toBeVisible()
  // The same registry the list renders from decides where to look, so a save that reloads the row
  // is waited out on the right control instead of by clicking the menu toggle in a retry loop.
  // 菜单里只有一项时列表直接显示成文字按钮，没有「操作 ▾」。
  if ((primaryActions.includes(name) || !(await menu.isVisible())) && await direct.isVisible()) {
    await direct.click()
    return
  }
  await menu.click()
  const option = page.getByRole('menuitem', { name, exact: true })
  if (primaryActions.includes(name)) {
    // 上一步保存后行还没刷新完就打开了菜单（如报价后「签约」由菜单外变成行内主按钮）：
    // 菜单展开完仍没有这一项时收起菜单，改点刷新后出现的行内按钮。
    const popper = page.locator('.el-dropdown__popper:visible')
    await expect(popper).toHaveCount(1)
    await expect(popper).not.toHaveClass(/-enter-active/)
    if (!(await option.isVisible())) {
      await menu.click()
      await expect(popper).toHaveCount(0)
      await direct.click()
      return
    }
  }
  await expect(option).toBeVisible()
  // 展开动画缩放期间，连续两帧坐标偶尔不变但菜单尚未展开到最终位置。
  // 等动画结束再点击，避免慢速 CI 中点击落在相邻条目或分组标题上。
  await expect(page.locator('.el-dropdown__popper').filter({ has: option })).not.toHaveClass(/-enter-active/)
  await option.click()
}

// 列表翻到第 n 页或最后一页。桌面点 el-pagination 的页码（首尾页码始终显示）；手机（≤600px）隐藏页码，
// 只有「上一页 / 第 n/m 页 / 下一页」，逐页点到目标页并核对页码提示。scope 取包含该列表分页的区域或弹窗。
export async function goToListPage(scope: Page | Locator, target: number | 'last') {
  const compact = scope.getByRole('group', { name: '翻页', exact: true })
  const pager = scope.locator('.el-pagination .el-pager')
  await expect(compact.or(pager).first()).toBeVisible()
  if (await compact.isVisible()) {
    const status = compact.getByText(/^第 \d+\/\d+ 页$/)
    const [current, total] = (await status.textContent())!.match(/(\d+)\/(\d+)/)!.slice(1).map(Number) as [number, number]
    const goal = target === 'last' ? total : target
    expect(goal, `目标页超出共 ${total} 页`).toBeLessThanOrEqual(total)
    const step = goal > current ? 1 : -1
    for (let page = current; page !== goal;) {
      page += step
      await compact.getByRole('button', { name: step > 0 ? '下一页' : '上一页', exact: true }).click()
      await expect(status).toHaveText(`第 ${page}/${total} 页`)
    }
    return
  }
  const goal = target === 'last' ? (await pager.locator('li.number').last().textContent())!.trim() : String(target)
  await pager.getByText(goal, { exact: true }).click()
  await expect(pager.locator('li.is-active')).toHaveText(goal)
}

// Import lives behind the toolbar's 导入导出 menu; one place so a toolbar change is one edit.
export async function openImport(page: Page) {
  await page.getByRole('button', { name: '导入导出 ▾', exact: true }).click()
  await page.getByRole('menuitem', { name: '导入', exact: true }).click()
}

export function observePage(page: Page, errors: string[]) {
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    const expected = expectedHttpErrors.get(page) || []
    const index = expected.findIndex(({ url, status }) =>
      message.type() === 'error' && message.location().url === url &&
      message.text().startsWith('Failed to load resource:') &&
      message.text().includes(`status of ${status} `),
    )
    if (index !== -1) {
      expected.splice(index, 1)
      return
    }
    if (['error', 'warning'].includes(message.type())) errors.push(message.text())
  })
}

export const test = base.extend<{ consoleCheck: void }>({
  consoleCheck: [async ({ context }, use) => {
    const errors: string[] = []
    const observe = (page: Page) => observePage(page, errors)
    context.pages().forEach(observe)
    context.on('page', observe)
    // 默认每页 20 条；这些流程按 10 条准备翻页数据，未显式选择时固定为 10 条，继续覆盖跨页行为。
    await context.addInitScript(() => {
      // 空白页和沙箱预览框读不到本地存储，那里也用不上分页设置。
      try { if (!localStorage.getItem('erp.page-size')) localStorage.setItem('erp.page-size', '10') } catch { /* 无存储的文档 */ }
    })
    await use()
    expect(errors, '浏览器不应出现运行异常或控制台警告').toEqual([])
  }, { auto: true }],
})
export { expect }
export type { Page, Locator } from '@playwright/test'

// 业务表单关闭时显式确认丢弃；未保存保护由 usability-forms 验证继续填写和恢复。
export async function cancelEditing(dialog: Locator) {
  const form = dialog.filter({ has: dialog.page().locator('form.action-form') })
  await form.getByRole('button', { name: '取消', exact: true }).click()
  const discard = dialog.page().getByRole('button', { name: '放弃修改', exact: true })
  await Promise.race([discard.waitFor({ state: 'visible' }), form.waitFor({ state: 'hidden' })])
  if (await discard.isVisible()) await discard.click()
  await expect(form).not.toBeVisible()
}

// 详情面板底部只平铺下一步，其余动作收在「更多操作」里；按名称点击，不关心它当前在哪。
export async function detailAction(page: Page, name: string) {
  const pane = page.getByRole('dialog')
  const direct = pane.getByRole('button', { name, exact: true })
  const more = pane.getByRole('button', { name: '更多操作 ▾', exact: true })
  await expect(direct.or(more).first()).toBeVisible()
  if (await direct.isVisible()) return direct.click()
  await more.click()
  await page.getByRole('menuitem', { name, exact: true }).click()
}

// 可搜索的人员下拉（Element Plus 单选或多选，如安装人、项目成员）：先清掉已选标签，按名称逐个输入过滤后点选；
// 多选最后点「完成选择」收起。名称须在候选里唯一，账号名会出现在选项标签里。
export async function choosePeople(page: Page, field: Locator, names: string[]) {
  const select = field.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " el-select ")][1]')
  // 编辑表单的已选人员在人员名单加载后才回填，先等请求结束再清空，避免把原有成员反选掉。
  await expect(field).toBeVisible()
  await page.waitForLoadState('networkidle')
  while (await select.locator('.el-tag__close').count()) await select.locator('.el-tag__close').first().click()
  await select.locator('.el-select__wrapper').click()
  const popper = page.locator('.el-select__popper.executor-options:visible')
  for (const name of names) {
    await field.fill(name)
    await expect(popper).not.toHaveClass(/-enter-active/)
    const option = popper.getByRole('option').filter({ hasText: name })
    await expect(option, `人员选项需唯一：${name}`).toHaveCount(1)
    await option.click()
  }
  const done = popper.getByRole('button', { name: '完成选择', exact: true })
  if (await done.count()) await done.click()
  await expect(page.locator('.el-select__popper.executor-options:visible')).toHaveCount(0)
}

// Select every executor by its visible label; replace the existing selection using tag close buttons.
export async function selectExecutors(page: Page, form: Locator, names: string[]) {
  const field = form.locator('.field').filter({ has: page.getByRole('combobox', { name: '执行人', exact: true }) }).first()
  const input = field.getByLabel('执行人', { exact: true })
  await expect(input).toBeVisible()
  while (await field.locator('.el-tag__close').count()) await field.locator('.el-tag__close').first().click()
  await expect(field.locator('.el-tag__close')).toHaveCount(0)
  // 多选后下拉保持打开；再次点击整个选择框的中心可能正好点击已选人员的删除图标。
  await field.locator('.el-select__wrapper').click()
  for (const name of names) {
    await input.fill(name)
    const option = page.getByRole('option', { name, exact: false })
    await expect(option).toBeVisible()
    await expect(page.locator('.el-select__popper.executor-options:visible')).not.toHaveClass(/-enter-active/)
    await option.click()
    await expect(option).toHaveAttribute('aria-selected', 'true')
    await expect(field.locator('.el-tag').filter({ hasText: name })).toHaveCount(1)
  }
  await page.locator('.executor-options:visible').getByRole('button', { name: '完成选择', exact: true }).click()
  await expect(page.locator('.executor-options:visible')).toHaveCount(0)
  await expect(field.locator('.el-tag__close')).toHaveCount(names.length)
}
