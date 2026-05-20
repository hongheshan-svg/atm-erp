import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '../user'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  getUserProfile: vi.fn(),
}))

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with null userInfo', () => {
      const store = useUserStore()
      expect(store.userInfo).toBeNull()
    })

    it('starts with profileReady false', () => {
      const store = useUserStore()
      expect(store.profileReady).toBe(false)
    })
  })

  describe('login', () => {
    it('stores tokens and user info on success', async () => {
      const { login: mockLogin } = await import('@/api/auth')
      ;(mockLogin as any).mockResolvedValue({
        data: {
          access: 'access-token-123',
          refresh: 'refresh-token-456',
          user: {
            id: 1,
            username: 'admin',
            is_superuser: true,
            permissions: ['*'],
            menus: ['dashboard'],
            data_scopes: {},
          },
        },
      })

      const store = useUserStore()
      const result = await store.login('admin', 'password')

      expect(result).toBe(true)
      expect(localStorage.getItem('access_token')).toBe('access-token-123')
      expect(localStorage.getItem('refresh_token')).toBe('refresh-token-456')
      expect(store.userInfo).not.toBeNull()
      expect(store.profileReady).toBe(true)
    })

    it('returns false on failure', async () => {
      const { login: mockLogin } = await import('@/api/auth')
      ;(mockLogin as any).mockRejectedValue(new Error('Invalid credentials'))

      const store = useUserStore()
      const result = await store.login('wrong', 'wrong')

      expect(result).toBe(false)
      expect(store.userInfo).toBeNull()
    })
  })

  describe('logout', () => {
    it('clears user state and storage', async () => {
      const store = useUserStore()
      store.userInfo = { id: 1, username: 'test' } as any
      store.profileReady = true
      localStorage.setItem('access_token', 'token')

      store.logout()

      expect(store.userInfo).toBeNull()
      expect(store.profileReady).toBe(false)
      expect(localStorage.getItem('access_token')).toBeNull()
    })
  })

  describe('getProfile', () => {
    it('fetches and stores profile', async () => {
      const { getUserProfile: mockGetProfile } = await import('@/api/auth')
      ;(mockGetProfile as any).mockResolvedValue({
        data: {
          id: 1,
          username: 'admin',
          is_superuser: true,
          permissions: ['*'],
          menus: ['dashboard'],
          data_scopes: { purchase: 'all' },
        },
      })

      const store = useUserStore()
      await store.getProfile()

      expect(store.userInfo).not.toBeNull()
      expect(store.profileReady).toBe(true)
    })
  })
})
