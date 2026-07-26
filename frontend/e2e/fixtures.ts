import { expect, test as base } from '@playwright/test'

type RuntimeConsoleFixtures = {
  allowedConsoleMessages: string[]
  runtimeConsoleGuard: void
}

export const test = base.extend<RuntimeConsoleFixtures>({
  allowedConsoleMessages: [[], { option: true }],
  runtimeConsoleGuard: [
    async ({ allowedConsoleMessages, page }, use) => {
      const runtimeMessages: string[] = []

      page.on('console', message => {
        if (message.type() === 'error' || message.type() === 'warning') {
          runtimeMessages.push(`${message.type()}: ${message.text()}`)
        }
      })
      page.on('pageerror', error => {
        runtimeMessages.push(`pageerror: ${error.message}`)
      })

      await use()
      const unexpectedMessages = runtimeMessages.filter(
        message => !allowedConsoleMessages.some(allowedMessage => message.includes(allowedMessage))
      )
      expect(unexpectedMessages).toEqual([])
    },
    { auto: true },
  ],
})

export { expect }
