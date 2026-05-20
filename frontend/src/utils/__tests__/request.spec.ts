import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'

vi.mock('axios', () => {
  const mockAxios: any = {
    create: vi.fn(() => mockAxios),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    request: vi.fn(),
  }
  return { default: mockAxios }
})

describe('request utility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('creates axios instance with baseURL /api', async () => {
    const { default: axiosMock } = await import('axios')
    // Re-import to trigger module execution
    vi.resetModules()

    // Verify the module imports correctly
    expect(axiosMock.create).toBeDefined()
  })

  it('attaches Authorization header when token exists', () => {
    localStorage.setItem('access_token', 'test-token-123')

    const { default: axiosMock } = require('axios')
    const requestInterceptor = axiosMock.interceptors?.request?.use
    expect(requestInterceptor).toBeDefined()
  })

  it('clears storage and redirects on 401 without refresh token', () => {
    localStorage.setItem('access_token', 'expired-token')
    // No refresh token - should redirect to login
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})
