import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'
import { loadEnv } from 'vite'

const rootEnv = loadEnv('', resolve(import.meta.dirname, '..'), '')
const useDocker = Boolean(process.env.E2E_BASE_URL || rootEnv.HTTP_PORT)
const httpPort = rootEnv.HTTP_PORT || '3000'

process.env.E2E_USERNAME ||= rootEnv.ADMIN_USERNAME || 'admin'
process.env.E2E_PASSWORD ||= rootEnv.ADMIN_PASSWORD

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  retries: 1,
  workers: 1,
  use: {
    baseURL: process.env.E2E_BASE_URL || `http://localhost:${httpPort}`,
    headless: true,
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
  },
  webServer: useDocker
    ? undefined
    : {
        command: 'npm run dev',
        port: 3000,
        reuseExistingServer: true,
        timeout: 120000,
      },
})
