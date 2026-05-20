import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Mock Element Plus message components
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn().mockResolvedValue('confirm'),
    alert: vi.fn().mockResolvedValue(undefined),
  },
  ElNotification: vi.fn(),
}))

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value }),
    removeItem: vi.fn((key: string) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock router
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    replace: vi.fn(),
    currentRoute: { value: { path: '/' } }
  }
}))

// Global test config for Vue Test Utils
config.global.stubs = {
  ElButton: true,
  ElTable: true,
  ElDialog: true,
  ElForm: true,
  ElFormItem: true,
  ElInput: true,
  ElSelect: true,
  ElOption: true,
  ElPagination: true,
  ElTag: true,
}
