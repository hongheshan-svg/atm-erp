import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import wsService from '@/utils/websocket'
import { ElNotification } from 'element-plus'
import type { Notification } from '@/types'

export const useWebSocketStore = defineStore('websocket', () => {
  const connected = ref(false)
  const notifications = ref<Notification[]>([])
  const unreadCount = ref(0)
  const dashboardData = ref<any>(null)

  const isConnected = computed(() => connected.value)
  const hasUnread = computed(() => unreadCount.value > 0)

  function connect(): void {
    wsService.connect('notifications')

    wsService.on('connection', handleConnection)
    wsService.on('notification', handleNotification)
    wsService.on('alert', handleAlert)
    wsService.on('error', handleError)
  }

  function connectDashboard(): DashboardWebSocket {
    const dashboardWs = new DashboardWebSocket()
    dashboardWs.connect('dashboard')
    dashboardWs.on('dashboard', handleDashboardUpdate)
    return dashboardWs
  }

  function disconnect(): void {
    wsService.disconnect()
    wsService.off('connection', handleConnection)
    wsService.off('notification', handleNotification)
    wsService.off('alert', handleAlert)
    wsService.off('error', handleError)
    connected.value = false
  }

  function handleConnection(data: { status: string }): void {
    connected.value = data.status === 'connected'
  }

  function handleNotification(notification: Notification): void {
    notifications.value.unshift(notification)
    unreadCount.value++

    const notifType = ({
      'INFO': 'info',
      'WARNING': 'warning',
      'ERROR': 'error',
      'SUCCESS': 'success'
    } as const)[notification.type] || 'info'

    ElNotification({
      title: notification.title,
      message: notification.message,
      type: notifType,
      duration: 5000,
      onClick: () => {
        markAsRead(notification.id)
      }
    })
  }

  function handleAlert(alert: { message: string }): void {
    ElNotification({
      title: 'System Alert',
      message: alert.message,
      type: 'warning',
      duration: 0,
    })
  }

  function handleDashboardUpdate(data: any): void {
    dashboardData.value = data
  }

  function handleError(error: any): void {
    console.error('WebSocket error:', error)
  }

  function markAsRead(notificationId: number): void {
    wsService.markNotificationRead(notificationId)

    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification && !notification.is_read) {
      notification.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  }

  function clearNotifications(): void {
    notifications.value = []
    unreadCount.value = 0
  }

  return {
    connected,
    notifications,
    unreadCount,
    dashboardData,
    isConnected,
    hasUnread,
    connect,
    connectDashboard,
    disconnect,
    markAsRead,
    clearNotifications
  }
})

class DashboardWebSocket {
  private ws: WebSocket | null = null
  private listeners: Record<string, Array<(data: any) => void>> = {}

  connect(endpoint: string): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/${endpoint}/`
    this.ws = new WebSocket(wsUrl)

    this.ws.onmessage = (event: MessageEvent) => {
      const data = JSON.parse(event.data)
      if (this.listeners[data.type]) {
        this.listeners[data.type].forEach(cb => cb(data.data))
      }
    }
  }

  on(event: string, callback: (data: any) => void): void {
    if (!this.listeners[event]) {
      this.listeners[event] = []
    }
    this.listeners[event].push(callback)
  }

  send(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
    }
  }
}
