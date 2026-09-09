import { test as base, expect, type Page } from '@playwright/test'

const expectedHttpErrors = new WeakMap<Page, { url: string; status: number }[]>()

export function expectHttpError(page: Page, path: string, status: number) {
  const expected = expectedHttpErrors.get(page) || []
  expected.push({ url: new URL(path, page.url()).href, status })
  expectedHttpErrors.set(page, expected)
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
