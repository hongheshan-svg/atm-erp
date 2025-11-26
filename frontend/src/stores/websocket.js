/**
 * Pinia store for WebSocket state management
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import wsService from '@/utils/websocket'
import { ElNotification } from 'element-plus'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const connected = ref(false)
  const notifications = ref([])
  const unreadCount = ref(0)
  const dashboardData = ref(null)

  // Computed
  const isConnected = computed(() => connected.value)
  const hasUnread = computed(() => unreadCount.value > 0)

  // Actions
  function connect() {
    // Connect to notifications WebSocket
    wsService.connect('notifications')
    
    // Set up event listeners
    wsService.on('connection', handleConnection)
    wsService.on('notification', handleNotification)
    wsService.on('alert', handleAlert)
    wsService.on('error', handleError)
  }

  function connectDashboard() {
    // Connect to dashboard WebSocket
    const dashboardWs = new WebSocketService()
    dashboardWs.connect('dashboard')
    dashboardWs.on('dashboard', handleDashboardUpdate)
    return dashboardWs
  }

  function disconnect() {
    wsService.disconnect()
    wsService.off('connection', handleConnection)
    wsService.off('notification', handleNotification)
    wsService.off('alert', handleAlert)
    wsService.off('error', handleError)
    connected.value = false
  }

  function handleConnection(data) {
    connected.value = data.status === 'connected'
    console.log('WebSocket connection status:', data.status)
  }

  function handleNotification(notification) {
    // Add to notifications array
    notifications.value.unshift(notification)
    unreadCount.value++
    
    // Show notification popup
    const notifType = {
      'INFO': 'info',
      'WARNING': 'warning',
      'ERROR': 'error',
      'SUCCESS': 'success'
    }[notification.type] || 'info'
    
    ElNotification({
      title: notification.title,
      message: notification.message,
      type: notifType,
      duration: 5000,
      onClick: () => {
        // Navigate to notification center or mark as read
        markAsRead(notification.id)
      }
    })
  }

  function handleAlert(alert) {
    // Handle system alerts
    ElNotification({
      title: 'System Alert',
      message: alert.message,
      type: 'warning',
      duration: 0, // Don't auto-close
    })
  }

  function handleDashboardUpdate(data) {
    dashboardData.value = data
  }

  function handleError(error) {
    console.error('WebSocket error:', error)
  }

  function markAsRead(notificationId) {
    wsService.markNotificationRead(notificationId)
    
    // Update local state
    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification && !notification.is_read) {
      notification.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  }

  function clearNotifications() {
    notifications.value = []
    unreadCount.value = 0
  }

  return {
    // State
    connected,
    notifications,
    unreadCount,
    dashboardData,
    // Computed
    isConnected,
    hasUnread,
    // Actions
    connect,
    connectDashboard,
    disconnect,
    markAsRead,
    clearNotifications
  }
})

// Separate WebSocketService instance for dashboard
class WebSocketService {
  constructor() {
    this.ws = null
    this.listeners = {}
  }

  connect(endpoint) {
    const wsUrl = `ws://localhost:8000/ws/${endpoint}/`
    this.ws = new WebSocket(wsUrl)
    
    this.ws.onopen = () => {
      console.log(`Connected to ${endpoint}`)
    }
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (this.listeners[data.type]) {
        this.listeners[data.type].forEach(cb => cb(data.data))
      }
    }
  }

  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = []
    }
    this.listeners[event].push(callback)
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
    }
  }
}

