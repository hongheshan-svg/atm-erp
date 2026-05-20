import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWebSocketStore } from '../websocket'

vi.mock('@/utils/websocket', () => ({
  default: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    markNotificationRead: vi.fn(),
  }
}))

describe('useWebSocketStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts disconnected', () => {
      const store = useWebSocketStore()
      expect(store.connected).toBe(false)
      expect(store.isConnected).toBe(false)
    })

    it('starts with no notifications', () => {
      const store = useWebSocketStore()
      expect(store.notifications).toEqual([])
      expect(store.unreadCount).toBe(0)
      expect(store.hasUnread).toBe(false)
    })
  })

  describe('connect', () => {
    it('calls wsService.connect', async () => {
      const wsService = await import('@/utils/websocket')
      const store = useWebSocketStore()

      store.connect()

      expect(wsService.default.connect).toHaveBeenCalledWith('notifications')
      expect(wsService.default.on).toHaveBeenCalledTimes(4)
    })
  })

  describe('disconnect', () => {
    it('calls wsService.disconnect and removes listeners', async () => {
      const wsService = await import('@/utils/websocket')
      const store = useWebSocketStore()

      store.disconnect()

      expect(wsService.default.disconnect).toHaveBeenCalled()
      expect(wsService.default.off).toHaveBeenCalledTimes(4)
      expect(store.connected).toBe(false)
    })
  })

  describe('markAsRead', () => {
    it('decrements unread count', async () => {
      const wsService = await import('@/utils/websocket')
      const store = useWebSocketStore()

      store.notifications = [
        { id: 1, title: 'Test', message: 'msg', type: 'INFO', is_read: false, created_at: '' }
      ]
      store.unreadCount = 1

      store.markAsRead(1)

      expect(store.unreadCount).toBe(0)
      expect(store.notifications[0].is_read).toBe(true)
      expect(wsService.default.markNotificationRead).toHaveBeenCalledWith(1)
    })

    it('does not go below zero', () => {
      const store = useWebSocketStore()
      store.unreadCount = 0
      store.notifications = [
        { id: 1, title: 'Test', message: 'msg', type: 'INFO', is_read: true, created_at: '' }
      ]

      store.markAsRead(1)

      expect(store.unreadCount).toBe(0)
    })
  })

  describe('clearNotifications', () => {
    it('empties notifications and resets count', () => {
      const store = useWebSocketStore()
      store.notifications = [
        { id: 1, title: 'A', message: 'b', type: 'INFO', is_read: false, created_at: '' }
      ]
      store.unreadCount = 5

      store.clearNotifications()

      expect(store.notifications).toEqual([])
      expect(store.unreadCount).toBe(0)
    })
  })
})
