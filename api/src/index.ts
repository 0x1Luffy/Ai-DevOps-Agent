import http from 'http'
import express from 'express'
import cors from 'cors'
import rateLimit from 'express-rate-limit'
import { Redis } from 'ioredis'

import { config } from './config'
import { pool, testConnection } from './db/client'
import { authMiddleware } from './middleware/auth'
import { errorHandler } from './middleware/errorHandler'
import { setupWebSocket, shutdownWebSocket } from './websocket/broadcaster'

import incidentsRouter from './routes/incidents'
import fixesRouter from './routes/fixes'
import clusterRouter from './routes/cluster'
import jenkinsRouter from './routes/jenkins'
import dashboardRouter from './routes/dashboard'
import metricsRouter from './routes/metrics'

const app = express()
const server = http.createServer(app)

// --- Redis setup ---
const redis = new Redis(config.redisUrl, {
  maxRetriesPerRequest: 3,
  enableReadyCheck: true,
  lazyConnect: true,
})

redis.on('connect', () => {
  console.log(`[${new Date().toISOString()}] Redis connected`)
})

redis.on('error', (err: Error) => {
  console.error(`[${new Date().toISOString()}] Redis error:`, err.message)
})

// Make redis available on app.locals for routes that need it
app.locals.redis = redis

// --- Core middleware ---
app.set('trust proxy', 1)

app.use(cors({
  origin: config.dashboardUrl,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}))

app.use(express.json({ limit: '1mb' }))
app.use(express.urlencoded({ extended: true }))

// Rate limiting
const limiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests', code: 'RATE_LIMITED' },
})
app.use(limiter)

// --- Health endpoint (before auth) ---
app.get('/health', async (_req, res) => {
  const [dbOk, redisStatus] = await Promise.all([
    testConnection(),
    redis.ping().then(() => 'ok').catch(() => 'error'),
  ])

  const status = dbOk && redisStatus === 'ok' ? 'ok' : 'degraded'
  res.status(status === 'ok' ? 200 : 503).json({
    status,
    timestamp: new Date().toISOString(),
    services: {
      postgres: dbOk ? 'ok' : 'error',
      redis: redisStatus,
    },
    version: '1.0.0',
  })
})

// --- Auth middleware (applied to all /api routes) ---
app.use('/api', authMiddleware)

// --- API routers ---
app.use('/api/incidents', incidentsRouter)
app.use('/api/fixes', fixesRouter)
app.use('/api/cluster', clusterRouter)
app.use('/api/jenkins', jenkinsRouter)
app.use('/api/dashboard', dashboardRouter)
app.use('/api/metrics', metricsRouter)

// 404 handler for unknown routes
app.use((_req, res) => {
  res.status(404).json({ error: 'Route not found', code: 'NOT_FOUND' })
})

// Error handler (must be last)
app.use(errorHandler)

// --- Startup ---
async function start(): Promise<void> {
  console.log(`[${new Date().toISOString()}] Starting AutoPilot Dashboard API...`)

  // Connect Redis
  try {
    await redis.connect()
    console.log(`[${new Date().toISOString()}] Redis connection established`)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error(`[${new Date().toISOString()}] Failed to connect to Redis: ${message}`)
    process.exit(1)
  }

  // Test PostgreSQL connection
  const dbOk = await testConnection()
  if (!dbOk) {
    console.error(`[${new Date().toISOString()}] Failed to connect to PostgreSQL. Exiting.`)
    process.exit(1)
  }
  console.log(`[${new Date().toISOString()}] PostgreSQL connection established`)

  // Set up WebSocket broadcaster (uses a separate Redis subscriber connection)
  const redisSub = new Redis(config.redisUrl, {
    maxRetriesPerRequest: 3,
    lazyConnect: true,
  })
  await redisSub.connect()
  setupWebSocket(server, redisSub)

  // Start HTTP server
  server.listen(config.port, () => {
    console.log(`[${new Date().toISOString()}] API server listening on port ${config.port}`)
    console.log(`[${new Date().toISOString()}] CORS origin: ${config.dashboardUrl}`)
    console.log(`[${new Date().toISOString()}] Agent URL: ${config.agentUrl}`)
  })
}

// --- Graceful shutdown ---
async function shutdown(signal: string): Promise<void> {
  console.log(`[${new Date().toISOString()}] Received ${signal}. Starting graceful shutdown...`)

  shutdownWebSocket()

  server.close(async () => {
    console.log(`[${new Date().toISOString()}] HTTP server closed`)

    try {
      await pool.end()
      console.log(`[${new Date().toISOString()}] PostgreSQL pool closed`)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.error(`[${new Date().toISOString()}] Error closing PostgreSQL pool: ${message}`)
    }

    try {
      await redis.quit()
      console.log(`[${new Date().toISOString()}] Redis connection closed`)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.error(`[${new Date().toISOString()}] Error closing Redis: ${message}`)
    }

    console.log(`[${new Date().toISOString()}] Graceful shutdown complete`)
    process.exit(0)
  })

  // Force exit after 15 seconds if graceful shutdown takes too long
  setTimeout(() => {
    console.error(`[${new Date().toISOString()}] Forced shutdown after timeout`)
    process.exit(1)
  }, 15000)
}

process.on('SIGTERM', () => { void shutdown('SIGTERM') })
process.on('SIGINT', () => { void shutdown('SIGINT') })

start().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err)
  console.error(`[${new Date().toISOString()}] Fatal startup error: ${message}`)
  process.exit(1)
})
