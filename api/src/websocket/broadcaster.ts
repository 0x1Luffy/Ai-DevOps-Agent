import { IncomingMessage, Server } from 'http'
import { WebSocket, WebSocketServer } from 'ws'
import { Redis } from 'ioredis'

interface ClientMeta {
  ws: WebSocket
  isAlive: boolean
  channels: Set<string>
}

const clients = new Map<WebSocket, ClientMeta>()

let heartbeatInterval: ReturnType<typeof setInterval> | null = null

function broadcast(event: unknown): void {
  const message = typeof event === 'string' ? event : JSON.stringify(event)
  for (const [ws, meta] of clients) {
    if (ws.readyState === WebSocket.OPEN) {
      // If client has channel subscriptions, filter; otherwise send all
      if (meta.channels.size === 0) {
        ws.send(message)
      } else {
        const parsed: unknown = typeof event === 'string' ? JSON.parse(event) : event
        const channel =
          parsed !== null &&
          typeof parsed === 'object' &&
          'channel' in parsed &&
          typeof (parsed as Record<string, unknown>)['channel'] === 'string'
            ? (parsed as Record<string, unknown>)['channel']
            : null
        if (!channel || meta.channels.has(channel as string)) {
          ws.send(message)
        }
      }
    }
  }
}

function setupHeartbeat(): void {
  heartbeatInterval = setInterval(() => {
    for (const [ws, meta] of clients) {
      if (!meta.isAlive) {
        // No pong received since last ping — close connection
        ws.terminate()
        clients.delete(ws)
        continue
      }
      meta.isAlive = false
      ws.ping()
    }
  }, 30000)
}

function handleClientMessage(ws: WebSocket, data: Buffer | string): void {
  try {
    const msg: unknown = JSON.parse(data.toString())
    if (
      msg !== null &&
      typeof msg === 'object' &&
      'type' in msg &&
      (msg as Record<string, unknown>)['type'] === 'subscribe' &&
      'channels' in msg &&
      Array.isArray((msg as Record<string, unknown>)['channels'])
    ) {
      const meta = clients.get(ws)
      if (meta) {
        const channels = (msg as Record<string, unknown[]>)['channels'] as unknown[]
        for (const ch of channels) {
          if (typeof ch === 'string') {
            meta.channels.add(ch)
          }
        }
        ws.send(JSON.stringify({ type: 'subscribed', channels: Array.from(meta.channels) }))
      }
    } else if (
      msg !== null &&
      typeof msg === 'object' &&
      'type' in msg &&
      (msg as Record<string, unknown>)['type'] === 'unsubscribe' &&
      'channels' in msg &&
      Array.isArray((msg as Record<string, unknown>)['channels'])
    ) {
      const meta = clients.get(ws)
      if (meta) {
        const channels = (msg as Record<string, unknown[]>)['channels'] as unknown[]
        for (const ch of channels) {
          if (typeof ch === 'string') {
            meta.channels.delete(ch)
          }
        }
        ws.send(JSON.stringify({ type: 'unsubscribed', channels: Array.from(meta.channels) }))
      }
    } else if (
      msg !== null &&
      typeof msg === 'object' &&
      'type' in msg &&
      (msg as Record<string, unknown>)['type'] === 'ping'
    ) {
      ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }))
    }
  } catch {
    // Ignore unparseable messages
  }
}

export function setupWebSocket(server: Server, redisClient: Redis): void {
  const wss = new WebSocketServer({ server, path: '/ws' })

  wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
    const clientIp = req.socket.remoteAddress ?? 'unknown'
    console.log(`[${new Date().toISOString()}] WebSocket client connected from ${clientIp}`)

    const meta: ClientMeta = {
      ws,
      isAlive: true,
      channels: new Set(),
    }
    clients.set(ws, meta)

    // Send initial connection ack
    ws.send(JSON.stringify({ type: 'connected', timestamp: new Date().toISOString() }))

    ws.on('pong', () => {
      const m = clients.get(ws)
      if (m) m.isAlive = true
    })

    ws.on('message', (data: Buffer | string) => {
      handleClientMessage(ws, data)
    })

    ws.on('close', () => {
      console.log(`[${new Date().toISOString()}] WebSocket client disconnected from ${clientIp}`)
      clients.delete(ws)
    })

    ws.on('error', (err: Error) => {
      console.error(`[${new Date().toISOString()}] WebSocket client error from ${clientIp}:`, err.message)
      clients.delete(ws)
    })
  })

  // Subscribe to Redis events channel
  redisClient.subscribe('autopilot:events', (err, count) => {
    if (err) {
      console.error(`[${new Date().toISOString()}] Failed to subscribe to Redis channel autopilot:events:`, err.message)
      return
    }
    console.log(`[${new Date().toISOString()}] Subscribed to Redis autopilot:events (${count} subscriptions)`)
  })

  redisClient.on('message', (channel: string, message: string) => {
    if (channel === 'autopilot:events') {
      try {
        const event: unknown = JSON.parse(message)
        broadcast(event)
      } catch {
        broadcast({ type: 'raw', channel, data: message })
      }
    }
  })

  setupHeartbeat()

  console.log(`[${new Date().toISOString()}] WebSocket server initialized on /ws`)
}

export { broadcast }

export function getConnectedClientCount(): number {
  return clients.size
}

export function shutdownWebSocket(): void {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval)
    heartbeatInterval = null
  }
  for (const [ws] of clients) {
    ws.close(1001, 'Server shutting down')
  }
  clients.clear()
}
