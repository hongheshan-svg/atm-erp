type EventCallback = (data: any) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private intentionalClose = false
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private listeners: Record<string, EventCallback[]> = {
    notification: [],
    dashboard: [],
    connection: [],
    error: [],
    alert: []
  }

  connect(endpoint = 'notifications'): void {
    const token = localStorage.getItem('access_token')
    if (!token) {
      console.error('No access token found')
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host || 'localhost:8000'
    const wsUrl = `${protocol}//${host}/ws/${endpoint}/?token=${token}`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.emit('connection', { status: 'connected', endpoint })
        this.startPingPong()
      }

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data)
          this.handleMessage(data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.ws.onerror = (error: Event) => {
        console.error('WebSocket error:', error)
        this.emit('error', error)
      }

      this.ws.onclose = () => {
        this.emit('connection', { status: 'disconnected', endpoint })
        if (this.intentionalClose) {
          this.intentionalClose = false
          return
        }
        this.attemptReconnect(endpoint)
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      this.emit('error', error)
    }
  }

  private handleMessage(data: { type: string; data?: any; message?: string }): void {
    const { type } = data

    switch (type) {
      case 'connection':
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
        break
    }
  }

  send(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  private startPingPong(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
    }

    this.pingInterval = setInterval(() => {
      this.send({
        type: 'ping',
        timestamp: new Date().toISOString()
      })
    }, 30000)
  }

  private attemptReconnect(endpoint: string): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => {
        this.connect(endpoint)
      }, this.reconnectDelay * this.reconnectAttempts)
    }
  }

  on(event: string, callback: EventCallback): void {
    if (!this.listeners[event]) {
      this.listeners[event] = []
    }
    this.listeners[event].push(callback)
  }

  off(event: string, callback: EventCallback): void {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback)
    }
  }

  private emit(event: string, data: any): void {
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

  disconnect(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
    }

    if (this.ws) {
      this.intentionalClose = true
      this.ws.close()
      this.ws = null
    }
  }

  markNotificationRead(notificationId: number): void {
    this.send({
      type: 'mark_read',
      notification_id: notificationId
    })
  }

  refreshDashboard(): void {
    this.send({
      type: 'refresh'
    })
  }
}

const wsService = new WebSocketService()

export default wsService
