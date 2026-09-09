import { test as base, expect, type Page } from '@playwright/test'
import { setTimeout as pause } from 'node:timers/promises'

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
