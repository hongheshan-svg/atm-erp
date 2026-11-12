import { test as base, expect, type APIRequestContext, type APIResponse, type BrowserContext, type Locator, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { setTimeout as pause } from 'node:timers/promises'
import { primaryActions } from '../src/row-actions'
import { selectRemoteOption } from './remote-select-helpers'

const expectedHttpErrors = new WeakMap<Page, { url: string; status: number }[]>()
const expectedFailures = new WeakMap<Page, string[]>()

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

// 模拟断网时浏览器对该路径（不含查询参数）的每次失败请求都会报一条控制台错误，次数取决于重试节奏；返回的函数结束容忍。
export function expectRequestFailures(page: Page, path: string) {
  const expected = expectedFailures.get(page) || []
  const pathname = new URL(path, page.url()).pathname
  expected.push(pathname)
  expectedFailures.set(page, expected)
  return () => { const index = expected.indexOf(pathname); if (index !== -1) expected.splice(index, 1) }
}

type Tokens = { access: string; refresh: string }
// 登录接口按来源 IP 每分钟限 10 次，整个分片共用这一额度：同一 worker 内按账号和密码复用令牌，
// 用例之间不再因为登录次数互相等待。
const sessions = new Map<string, Tokens>()

// 被限流（429）时按 Retry-After 等待后重发，其余结果原样交给调用方断言。
async function retryThrottled(send: () => Promise<APIResponse>) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const response = await send()
    if (response.status() !== 429) return response
    const seconds = Number(response.headers()['retry-after'])
    expect(seconds).toBeGreaterThan(0)
    expect(seconds).toBeLessThanOrEqual(60)
    await pause(seconds * 1000 + 200)
  }
  throw new Error('服务器限流等待后仍未恢复。')
}

// 经接口登录一次（不读缓存）；status 用于断言预期的拒绝。
export async function apiLogin(request: APIRequestContext, username: string, password: string, status = 200): Promise<Tokens> {
  const response = await retryThrottled(() => request.post('/api/auth/login/', { data: { username, password } }))
  expect(response.status(), await response.text()).toBe(status)
  return response.json()
}

// 取该账号可用的令牌：已登录过的先续期（同时确认登录仍有效，改密或停用后续期失败即重新登录），否则登录一次。
export async function accountTokens(request: APIRequestContext, username: string, password: string): Promise<Tokens> {
  const key = JSON.stringify([username, password])
  const cached = sessions.get(key)
  if (cached) {
    const renewed = await retryThrottled(() => request.post('/api/auth/refresh/', { data: { refresh: cached.refresh } }))
    if (renewed.ok()) {
      const current = { ...cached, access: (await renewed.json()).access as string }
      sessions.set(key, current)
      return current
    }
    sessions.delete(key)
  }
  const { access, refresh } = await apiLogin(request, username, password)
  sessions.set(key, { access, refresh })
  return { access, refresh }
}

// 以指定账号进入工作台。令牌经接口取得并写入本页的登录存储；登录表单本身由 login.spec 经 loginThroughForm 验证。
export async function login(page: Page, username: string, password: string) {
  const { access, refresh } = await accountTokens(page.request, username, password)
  // 登录页不发业务请求，在这里换上令牌，再整页载入工作台，与登录表单成功后的状态一致。
  await page.goto('/erp/login')
  await page.evaluate(([access, refresh]) => {
    localStorage.setItem('access_token', access!)
    localStorage.setItem('refresh_token', refresh!)
    // 与表单登录一致：换账号时清掉上一账号未提交的表单暂存。
    for (let index = sessionStorage.length - 1; index >= 0; index--) {
      const key = sessionStorage.key(index)
      if (key?.startsWith('erp-form-draft:')) sessionStorage.removeItem(key)
    }
  }, [access, refresh])
  await page.goto('/erp/workbench')
  await expect(page).toHaveURL(/workbench/)
}

// 从登录页提交账号密码，返回登录接口的最终响应；被限流时核对页面提示，按 Retry-After 等待后重新提交。
// status 为预期结果：200 时等进入工作台，其余（如 401）登记为预期的控制台错误并等页面显示错误提示。
export async function loginThroughForm(page: Page, username: string, password: string, status = 200) {
  await page.goto('/erp/login')
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  if (status >= 400) expectHttpError(page, '/api/auth/login/', status)
  for (let attempt = 0; attempt < 3; attempt++) {
    const stopExpecting = expectHttpError(page, '/api/auth/login/', 429)
    const pending = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/login/' && r.request().method() === 'POST')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    const response = await pending
    if (response.status() !== 429) {
      stopExpecting()
      expect(response.status(), await response.text()).toBe(status)
      if (status === 200) await expect(page).toHaveURL(/workbench/)
      else await expect(page.getByRole('alert')).toBeVisible()
      return response
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

// 以给定访问令牌调用接口的客户端，不依赖页面登录状态；路径写完整，如 /api/business/partners/。
export function apiClient(request: APIRequestContext, token: string) {
  const headers = { Authorization: `Bearer ${token}` }
  return {
    headers,
    async get(path: string) {
      const response = await request.get(path, { headers })
      expect(response.status(), `${path}: ${await response.text()}`).toBe(200)
      return response.json()
    },
    async post(path: string, data: object, status = 201, key: string = randomUUID()) {
      const response = await request.post(path, { headers: { ...headers, 'Idempotency-Key': key }, data })
      expect(response.status(), `${path}: ${await response.text()}`).toBe(status)
      return response.json()
    },
  }
}
export type ApiClient = ReturnType<typeof apiClient>

// 以账号身份取得接口客户端；令牌与 login() 共用缓存，不额外占用登录限流额度。
export async function authenticate(request: APIRequestContext, username: string, password: string) {
  return apiClient(request, (await accountTokens(request, username, password)).access)
}

// 用页面当前登录账号的令牌调用接口：不带 data 为 GET，带 data 为 POST（附幂等键）；path 相对 /api/。
export async function api(page: Page, path: string, data?: object, status = 200) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': randomUUID() }
  const response = data === undefined
    ? await page.request.get('/api/' + path, { headers })
    : await page.request.post('/api/' + path, { headers, data })
  expect(response.status(), await response.text()).toBe(status)
  return response.json()
}

// 点当前对话框的提交按钮并等这次写入的响应。path（相对 /api/ 或以 / 开头的完整路径）按完整路径匹配；
// 省略时取第一个写请求，但不取登录与令牌续期，免得把后台续期当成保存结果。
// status 省略时接受 2xx；给定时精确比较，≥400 同时登记为预期的控制台错误。成功后等所有对话框关闭。
export async function submitDialog(page: Page, path?: string, status?: number, dialog: Locator = page.getByRole('dialog')) {
  const target = path && (path.startsWith('/') ? path : '/api/' + path)
  if (target && status && status >= 400) expectHttpError(page, target, status)
  const pending = page.waitForResponse(response => {
    if (!['POST', 'PATCH'].includes(response.request().method())) return false
    const pathname = new URL(response.url()).pathname
    return target ? pathname === target : pathname.startsWith('/api/') && !['/api/auth/login/', '/api/auth/refresh/'].includes(pathname)
  })
  await dialog.locator('button[type="submit"]').click()
  const response = await pending
  if (status) expect(response.status(), await response.text()).toBe(status)
  else expect(response.status(), await response.text()).toBeLessThan(300)
  if (response.status() < 300) await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0)
  return response.json()
}

// 按字段名选择当前对话框里的值：远程资料下拉按名称搜索点选，可搜索人员下拉用 choosePeople，原生下拉取最后一个文本匹配的选项。
export async function choose(page: Page, label: string, text: string) {
  const field = page.getByRole('dialog').getByLabel(label, { exact: true })
  if (await field.getAttribute('role') === 'combobox') {
    // 远程资料下拉与可搜索的人员下拉都是 combobox，后者没有 remote-select 外壳。
    const remote = await field.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " remote-select ")]').count()
    return remote ? selectRemoteOption(field, { text }) : choosePeople(page, field, [text])
  }
  const value = await field.locator('option').filter({ hasText: text }).last().getAttribute('value')
  await field.selectOption(value!)
}

// 在列表面板里按关键词搜索并等结果返回。列表加载中「搜索」按钮处于禁用态，此时回车不会提交表单，
// 所以先等上一次加载（如保存后的刷新、进页加载）结束。
export async function searchList(page: Page, title: string, text: string) {
  const panel = page.getByRole('region', { name: title, exact: true })
  await expect(panel.getByRole('button', { name: '搜索', exact: true })).toBeEnabled()
  const box = panel.getByRole('searchbox', { name: `搜索${title}`, exact: true })
  await box.fill(text)
  const searched = page.waitForResponse(r => r.request().method() === 'GET' && new URL(r.url()).searchParams.get('search') === text)
  await box.press('Enter')
  expect((await searched).status()).toBe(200)
  return panel
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
    if (message.type() === 'error' && message.text().startsWith('Failed to load resource:')) {
      const expected = expectedHttpErrors.get(page) || []
      const index = expected.findIndex(({ url, status }) =>
        message.location().url === url && message.text().includes(`status of ${status} `),
      )
      if (index !== -1) {
        expected.splice(index, 1)
        return
      }
      const location = message.location().url
      if (location && (expectedFailures.get(page) || []).includes(new URL(location).pathname) && message.text().includes('net::ERR_FAILED')) return
    }
    if (['error', 'warning'].includes(message.type())) errors.push(message.text())
  })
}

type Session = (username: string, password: string, options?: { timezoneId?: string }) => Promise<Page>
export const test = base.extend<{ consoleCheck: void; session: Session }>({
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
  // 另开浏览器上下文以其他账号登录（视口与触屏同当前项目），用例结束时统一关闭并核对这些页面的控制台。
  session: async ({ browser }, use, info) => {
    const contexts: BrowserContext[] = []
    const errors: string[] = []
    await use(async (username, password, options = {}) => {
      const { baseURL, viewport, isMobile, hasTouch } = info.project.use
      const context = await browser.newContext({ baseURL, viewport, isMobile, hasTouch, timezoneId: options.timezoneId })
      contexts.push(context)
      const page = await context.newPage()
      observePage(page, errors)
      await login(page, username, password)
      return page
    })
    for (const context of contexts) await context.close()
    expect(errors, '其他账号的页面不应出现运行异常或控制台警告').toEqual([])
  },
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

// 可搜索的人员下拉（Element Plus 单选或多选，如安装人、项目成员）：按名称逐个输入过滤后点选，名称须在候选里唯一，
// 账号名会出现在选项标签里。多选先取消已选人员再选，最后点「完成选择」收起。
export async function choosePeople(page: Page, field: Locator, names: string[]) {
  const select = field.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " el-select ")][1]')
  await expect(field).toBeVisible()
  while (await select.locator('.el-tag__close').count()) await select.locator('.el-tag__close').first().click()
  await select.locator('.el-select__wrapper').click()
  const popper = page.locator('.el-select__popper.executor-options:visible')
  await expect(popper).toHaveCount(1)
  await expect(popper).not.toHaveClass(/-enter-active/)
  const done = popper.getByRole('button', { name: '完成选择', exact: true })
  const multiple = await done.count() > 0
  const footer = popper.locator('.executor-options-footer')
  if (multiple) {
    // 人员名单和已选人员随对话框一起给出，但已选标签可能晚一拍才渲染：以选项的选中状态（直接取自表单值）为准，
    // 取消清标签时还没显示出来的人员，不靠等网络空闲。
    const selected = popper.getByRole('option', { selected: true })
    while (await selected.count()) await selected.first().click()
    await expect(footer).toContainText('已选 0 人')
  }
  for (const name of names) {
    await field.fill(name)
    await expect(popper).not.toHaveClass(/-enter-active/)
    const option = popper.getByRole('option').filter({ hasText: name })
    await expect(option, `人员选项需唯一：${name}`).toHaveCount(1)
    await option.click()
    if (multiple) await expect(option).toHaveAttribute('aria-selected', 'true')
  }
  if (multiple) {
    await expect(footer).toContainText(`已选 ${names.length} 人`)
    await done.click()
  }
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
