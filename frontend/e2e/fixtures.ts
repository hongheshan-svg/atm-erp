import { test as base, expect, type Locator, type Page } from '@playwright/test'
import { setTimeout as pause } from 'node:timers/promises'
import { primaryActions } from '../src/row-actions'

const expectedHttpErrors = new WeakMap<Page, { url: string; status: number }[]>()

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
  const direct = row.getByRole('button', { name, exact: true })
  await expect(direct.or(menu).first()).toBeVisible()
  // The same registry the list renders from decides where to look, so a save that reloads the row
  // is waited out on the right control instead of by clicking the menu toggle in a retry loop.
  if (primaryActions.includes(name)) {
    await direct.click()
    return
  }
  await menu.click()
  await page.getByRole('menuitem', { name, exact: true }).click()
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
    await use()
    expect(errors, '浏览器不应出现运行异常或控制台警告').toEqual([])
  }, { auto: true }],
})
export { expect }
export type { Page, Locator } from '@playwright/test'
