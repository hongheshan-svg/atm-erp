import { defineConfig } from '@playwright/test'
if (!process.env.E2E_BASE_URL) throw new Error('请显式设置 E2E_BASE_URL，且只能使用隔离测试安装。')
if (!process.env.E2E_ADMIN_PASSWORD) throw new Error('请显式设置隔离测试安装的 E2E_ADMIN_PASSWORD。')
export default defineConfig({
  testDir: './e2e',
  timeout: 120000,
  retries: 0,
  workers: 1,
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  use: {
    actionTimeout: 15000,
    baseURL: process.env.E2E_BASE_URL,
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
