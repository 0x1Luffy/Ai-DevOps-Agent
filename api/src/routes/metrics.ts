import { Router, Request, Response, NextFunction } from 'express'
import { z } from 'zod'
import { query } from '../db/client'
import { createError } from '../middleware/errorHandler'
import { ratio } from '../utils/shape'

const router = Router()

const TrendsQuerySchema = z.object({
  days: z.coerce.number().int().positive().max(90).default(7),
})

// GET /api/metrics/trends
router.get('/trends', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const parsed = TrendsQuerySchema.safeParse(req.query)
    if (!parsed.success) {
      return next(createError(parsed.error.errors[0]?.message ?? 'Invalid query params', 400, 'VALIDATION_ERROR'))
    }
    const { days } = parsed.data
    const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString()

    const [incidentsByDayRes, fixSuccessByDayRes, mttrRes, topNamespacesRes] = await Promise.all([
      // Incidents grouped by day and severity
      query<{ date: string; severity: string; count: string }>(
        `SELECT
           DATE(detected_at) AS date,
           severity,
           COUNT(*) AS count
         FROM incidents
         WHERE detected_at >= $1
         GROUP BY DATE(detected_at), severity
         ORDER BY date ASC`,
        [since]
      ),
      // Fix success rate by day
      query<{ date: string; success: string; total: string }>(
        `SELECT
           DATE(executed_at) AS date,
           COUNT(*) FILTER (WHERE result = 'success') AS success,
           COUNT(*) AS total
         FROM fix_executions
         WHERE executed_at >= $1
         GROUP BY DATE(executed_at)
         ORDER BY date ASC`,
        [since]
      ),
      // Mean time to resolution by day
      query<{ date: string; avg_minutes: string }>(
        `SELECT
           DATE(resolved_at) AS date,
           AVG(EXTRACT(EPOCH FROM (resolved_at - detected_at)) / 60) AS avg_minutes
         FROM incidents
         WHERE resolved_at IS NOT NULL
           AND detected_at IS NOT NULL
           AND resolved_at >= $1
         GROUP BY DATE(resolved_at)
         ORDER BY date ASC`,
        [since]
      ),
      // Top namespaces by incident count
      query<{ namespace: string; incident_count: string }>(
        `SELECT
           namespace,
           COUNT(*) AS incident_count
         FROM incidents
         WHERE detected_at >= $1
         GROUP BY namespace
         ORDER BY incident_count DESC
         LIMIT 10`,
        [since]
      ),
    ])

    // Aggregate incidents by day with by_severity breakdown
    type DaySeverityMap = Record<string, Record<string, number>>
    const dayMap: DaySeverityMap = {}
    for (const row of incidentsByDayRes.rows) {
      if (!dayMap[row.date]) {
        dayMap[row.date] = {}
      }
      dayMap[row.date]![row.severity] = parseInt(row.count, 10)
    }

    // Also get total per day
    const dayTotals: Record<string, number> = {}
    for (const row of incidentsByDayRes.rows) {
      dayTotals[row.date] = (dayTotals[row.date] ?? 0) + parseInt(row.count, 10)
    }

    const incidentsByDay = Object.keys(dayMap)
      .sort()
      .map((date) => ({
        date,
        count: dayTotals[date] ?? 0,
        by_severity: dayMap[date] ?? {},
      }))

    const fixSuccessByDay = fixSuccessByDayRes.rows.map((row) => {
      const total = parseInt(row.total, 10)
      const success = parseInt(row.success, 10)
      return {
        date: row.date,
        successRate: ratio(success, total) * 100,
      }
    })

    const mttr = mttrRes.rows.map((row) => ({
      date: row.date,
      avgMinutes: parseFloat(parseFloat(row.avg_minutes).toFixed(2)),
    }))

    const topNamespaces = topNamespacesRes.rows.map((row) => ({
      namespace: row.namespace,
      incidentCount: parseInt(row.incident_count, 10),
    }))

    res.json({
      incidentsByDay,
      fixSuccessByDay,
      mttr,
      topNamespaces,
    })
  } catch (err) {
    next(err)
  }
})

export default router
