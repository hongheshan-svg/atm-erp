/**
 * WebSocket service for real-time notifications and updates
 */
class WebSocketService {
  constructor() {
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 3000
    this.listeners = {
      notification: [],
      dashboard: [],
      connection: [],
      error: []
    }
  }

  /**
   * Connect to WebSocket server
   */
  connect(endpoint = 'notifications') {
    const token = localStorage.getItem('access_token')
    if (!token) {
      console.error('No access token found')
      return
    }

    // 使用当前域名和协议，兼容开发和生产环境
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host || 'localhost:8000'
    const wsUrl = `${protocol}//${host}/ws/${endpoint}/`
    
    try {
      this.ws = new WebSocket(wsUrl)
      
      this.ws.onopen = () => {
        console.log(`WebSocket connected to ${endpoint}`)
        this.reconnectAttempts = 0
        this.emit('connection', { status: 'connected', endpoint })
        
        // Start ping/pong to keep connection alive
        this.startPingPong()
      }
      
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.handleMessage(data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.emit('error', error)
      }
      
      this.ws.onclose = () => {
        console.log('WebSocket connection closed')
        this.emit('connection', { status: 'disconnected', endpoint })
        this.attemptReconnect(endpoint)
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      this.emit('error', error)
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  handleMessage(data) {
    const { type } = data
    
    switch (type) {
      case 'connection':
        console.log('Connection confirmed:', data.message)
        break
      
      case 'notification':
        this.emit('notification', data.data)
        break
      
      case 'alert':
        this.emit('alert', data.data)
        break
      
      case 'dashboard_data':
      case 'dashboard_update':
        this.emit('dashboard', data.data)
        break
      
      case 'pong':
        // Handle pong response
        break
      
      default:
        console.log('Unknown message type:', type)
    }
  }

  /**
   * Send message to WebSocket server
   */
  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.error('WebSocket is not connected')
    }
  }

  /**
   * Start ping/pong to keep connection alive
   */
  startPingPong() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
    }
    
    this.pingInterval = setInterval(() => {
      this.send({
        type: 'ping',
        timestamp: new Date().toISOString()
      })
    }, 30000) // Ping every 30 seconds
  }

  /**
   * Attempt to reconnect to WebSocket
   */
  attemptReconnect(endpoint) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      
      setTimeout(() => {
        this.connect(endpoint)
      }, this.reconnectDelay * this.reconnectAttempts)
    } else {
      console.error('Max reconnection attempts reached')
    }
  }

  /**
   * Register event listener
   */
  on(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].push(callback)
    }
  }

  /**
   * Unregister event listener
   */
  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback)
    }
  }

  /**
   * Emit event to all registered listeners
   */
  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in ${event} listener:`, error)
        }
      })
    }
  }

  /**
   * Disconnect WebSocket
   */
  disconnect() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
    }
    
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * Mark notification as read
   */
  markNotificationRead(notificationId) {
    this.send({
      type: 'mark_read',
      notification_id: notificationId
    })
  }

  /**
   * Request dashboard refresh
   */
  refreshDashboard() {
    this.send({
      type: 'refresh'
    })
  }
}

// Create singleton instance
const wsService = new WebSocketService()

export default wsService

