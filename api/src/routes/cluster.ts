import { Router, Request, Response, NextFunction } from 'express'
import axios from 'axios'
import { Redis } from 'ioredis'
import { query } from '../db/client'
import { config } from '../config'
import { createError } from '../middleware/errorHandler'

const router = Router()

const HEALTH_CACHE_KEY = 'cache:cluster:health'
const HEALTH_CACHE_TTL = 30 // seconds

function getRedis(req: Request): Redis {
  return req.app.locals.redis as Redis
}

// GET /api/cluster/health
router.get('/health', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const redis = getRedis(req)

    // Check cache first
    const cached = await redis.get(HEALTH_CACHE_KEY)
    if (cached) {
      const parsed: unknown = JSON.parse(cached)
      res.json(parsed)
      return
    }

    // Fetch from agent
    const response = await axios.get(`${config.agentUrl}/cluster/health-gate`, {
      timeout: 10000,
    })

    const data: unknown = response.data

    // Cache for 30 seconds
    await redis.setex(HEALTH_CACHE_KEY, HEALTH_CACHE_TTL, JSON.stringify(data))

    res.json(data)
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status ?? 503
      return next(createError(
        `Failed to fetch cluster health from agent: ${err.message}`,
        status,
        'AGENT_UNAVAILABLE'
      ))
    }
    next(err)
  }
})

// GET /api/cluster/nodes
router.get('/nodes', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const response = await axios.get(`${config.agentUrl}/cluster/nodes`, {
      timeout: 10000,
    })

    res.json(response.data)
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status ?? 503
      return next(createError(
        `Failed to fetch cluster nodes from agent: ${err.message}`,
        status,
        'AGENT_UNAVAILABLE'
      ))
    }
    next(err)
  }
})

// GET /api/cluster/namespaces
router.get('/namespaces', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const result = await query<{
      namespace: string
      open_incidents: string
      critical_incidents: string
    }>(
      `SELECT
         namespace,
         COUNT(*) FILTER (WHERE status IN ('open', 'fixing', 'needs_approval')) AS open_incidents,
         COUNT(*) FILTER (WHERE severity = 'critical' AND status IN ('open', 'fixing', 'needs_approval')) AS critical_incidents
       FROM incidents
       GROUP BY namespace
       ORDER BY open_incidents DESC`
    )

    const namespaces = result.rows.map((row) => {
      const openIncidents = parseInt(row.open_incidents, 10)
      const criticalIncidents = parseInt(row.critical_incidents, 10)

      let status: string
      if (criticalIncidents > 0) {
        status = 'critical'
      } else if (openIncidents > 0) {
        status = 'degraded'
      } else {
        status = 'healthy'
      }

      return {
        namespace: row.namespace,
        openIncidents,
        criticalIncidents,
        totalPods: null, // placeholder — would require live k8s data
        status,
      }
    })

    res.json(namespaces)
  } catch (err) {
    next(err)
  }
})

export default router
