/**
 * WebSocket Client for Real-Time Analysis Progress
 */

import type { WebSocketProgressMessage, PRWithPriority } from '@/types/api'

export type WebSocketCallbacks = {
  onProgress?: (current: number, total: number, status: string) => void
  onComplete?: (results: PRWithPriority[]) => void
  onError?: (error: string) => void
  onConnected?: () => void
  onDisconnected?: () => void
}

export class AnalysisWebSocket {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 2000
  private callbacks: WebSocketCallbacks = {}

  constructor(url: string | undefined = undefined) {
    // Determine WebSocket URL based on environment
    if (url) {
      this.url = url
    } else if (import.meta.env.DEV) {
      this.url = 'ws://127.0.0.1:8000/ws/analyze'
    } else {
      // In production, use ws:// or wss:// based on current protocol
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      this.url = `${protocol}//${host}/ws/analyze`
    }
  }

  connect(callbacks: WebSocketCallbacks = {}) {
    this.callbacks = callbacks

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.callbacks.onConnected?.()
        console.log('WebSocket connected to', this.url)
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketProgressMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        this.callbacks.onError?.('WebSocket connection error')
      }

      this.ws.onclose = () => {
        this.callbacks.onDisconnected?.()
        console.log('WebSocket disconnected')

        // Attempt to reconnect
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          console.log(`Reconnecting... Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`)
          setTimeout(() => {
            this.connect(this.callbacks)
          }, this.reconnectDelay)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      this.callbacks.onError?.('Failed to connect to WebSocket')
    }
  }

  private handleMessage(message: WebSocketProgressMessage) {
    switch (message.type) {
      case 'progress':
        if (message.current !== undefined && message.total !== undefined && message.status) {
          this.callbacks.onProgress?.(message.current, message.total, message.status)
        }
        break

      case 'complete':
        if (message.results) {
          this.callbacks.onComplete?.(message.results)
        }
        break

      case 'error':
        if (message.error) {
          this.callbacks.onError?.(message.error)
        }
        break

      case 'subscribed':
        console.log('Subscribed to analysis:', message.analysis_id)
        break

      case 'pong':
        // Server responded to ping
        break

      default:
        console.log('Unknown message type:', message.type)
    }
  }

  subscribe(analysisId: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        analysis_id: analysisId
      }))
    }
  }

  ping() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'ping' }))
    }
  }

  disconnect() {
    this.reconnectAttempts = this.maxReconnectAttempts // Prevent reconnection
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}
