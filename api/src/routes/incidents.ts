import { Router, Request, Response, NextFunction } from 'express'
import { z } from 'zod'
import { query } from '../db/client'
import { createError } from '../middleware/errorHandler'
import { toCamel } from '../utils/shape'

const router = Router()

const ListQuerySchema = z.object({
  namespace: z.string().optional(),
  severity: z.string().optional(),
  status: z.string().optional(),
  problem_type: z.string().optional(),
  problemType: z.string().optional(),
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().positive().max(100).default(20),
  from_date: z.string().datetime({ offset: true }).optional(),
  to_date: z.string().datetime({ offset: true }).optional(),
  from: z.string().optional(),
  to: z.string().optional(),
  search: z.string().optional(),
})

// GET /api/incidents
router.get('/', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const parsed = ListQuerySchema.safeParse(req.query)
    if (!parsed.success) {
      return next(createError(parsed.error.errors[0]?.message ?? 'Invalid query params', 400, 'VALIDATION_ERROR'))
    }
    const { namespace, page, limit, search } = parsed.data
    const severity = parsed.data.severity?.toUpperCase()
    const status = parsed.data.status
    const problemType = parsed.data.problem_type ?? parsed.data.problemType
    const fromDate = parsed.data.from_date ?? parsed.data.from
    const toDate = parsed.data.to_date ?? parsed.data.to

    const conditions: string[] = []
    const params: unknown[] = []
    let idx = 1

    if (namespace) {
      conditions.push(`namespace = $${idx++}`)
      params.push(namespace)
    }
    if (severity) {
      conditions.push(`severity = $${idx++}`)
      params.push(severity)
    }
    if (status) {
      conditions.push(`status = $${idx++}`)
      params.push(status)
    }
    if (problemType) {
      conditions.push(`problem_type = $${idx++}`)
      params.push(problemType)
    }
    if (fromDate) {
      conditions.push(`detected_at >= $${idx++}`)
      params.push(fromDate)
    }
    if (toDate) {
      conditions.push(`detected_at <= $${idx++}`)
      params.push(toDate)
    }
    if (search) {
      conditions.push(`(resource_name ILIKE $${idx} OR problem_type ILIKE $${idx} OR namespace ILIKE $${idx})`)
      params.push(`%${search}%`)
      idx++
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

    const countResult = await query<{ count: string }>(
      `SELECT COUNT(*) as count FROM incidents ${whereClause}`,
      params
    )
    const total = parseInt(countResult.rows[0]?.count ?? '0', 10)
    const totalPages = Math.ceil(total / limit)
    const offset = (page - 1) * limit

    const dataResult = await query(
      `SELECT * FROM incidents ${whereClause} ORDER BY detected_at DESC LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, limit, offset]
    )

    res.json({
      incidents: toCamel(dataResult.rows),
      total,
      page,
      totalPages,
    })
  } catch (err) {
    next(err)
  }
})

// GET /api/incidents/stats
router.get('/stats', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const [totalRes, statusRes, severityRes, problemRes, resolutionRes] = await Promise.all([
      query<{ count: string }>('SELECT COUNT(*) as count FROM incidents'),
      query<{ status: string; count: string }>('SELECT status, COUNT(*) as count FROM incidents GROUP BY status'),
      query<{ severity: string; count: string }>('SELECT severity, COUNT(*) as count FROM incidents GROUP BY severity'),
      query<{ problem_type: string; count: string }>(
        'SELECT problem_type, COUNT(*) as count FROM incidents GROUP BY problem_type ORDER BY count DESC'
      ),
      query<{ avg_minutes: string }>(
        `SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - detected_at)) / 60) as avg_minutes
         FROM incidents
         WHERE resolved_at IS NOT NULL AND detected_at IS NOT NULL`
      ),
    ])

    const total = parseInt(totalRes.rows[0]?.count ?? '0', 10)
    const statusMap: Record<string, number> = {}
    for (const row of statusRes.rows) {
      statusMap[row.status] = parseInt(row.count, 10)
    }

    const bySeverity: Record<string, number> = {}
    for (const row of severityRes.rows) {
      bySeverity[row.severity] = parseInt(row.count, 10)
    }

    const byProblemType: Record<string, number> = {}
    for (const row of problemRes.rows) {
      byProblemType[row.problem_type] = parseInt(row.count, 10)
    }

    const avgResolutionRaw = resolutionRes.rows[0]?.avg_minutes
    const avg_resolution_time_minutes = avgResolutionRaw ? parseFloat(parseFloat(avgResolutionRaw).toFixed(2)) : null

    res.json({
      total,
      open: statusMap['open'] ?? 0,
      fixing: statusMap['fixing'] ?? 0,
      fixed: statusMap['fixed'] ?? 0,
      bySeverity,
      byProblemType,
      avgResolutionTimeMinutes: avg_resolution_time_minutes,
    })
  } catch (err) {
    next(err)
  }
})

// GET /api/incidents/:id
router.get('/:id', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const { id } = req.params

    const incidentRes = await query('SELECT * FROM incidents WHERE id = $1', [id])
    if (incidentRes.rows.length === 0) {
      return next(createError('Incident not found', 404, 'NOT_FOUND'))
    }
    const incident = incidentRes.rows[0]

    const fixesRes = await query(
      'SELECT * FROM fix_executions WHERE incident_id = $1 ORDER BY executed_at ASC',
      [id]
    )

    // Build chronological timeline of events
    type TimelineEvent = {
      timestamp: Date | string | null
      event: string
      detail: string
    }

    const timeline: TimelineEvent[] = []

    if (incident.detected_at) {
      timeline.push({
        timestamp: incident.detected_at,
        event: 'detected',
        detail: `Incident detected: ${incident.problem_type as string} in ${incident.namespace as string}/${incident.resource_name as string}`,
      })
    }

    for (const fix of fixesRes.rows) {
      if (fix.executed_at) {
        timeline.push({
          timestamp: fix.executed_at as Date,
          event: 'fix_applied',
          detail: `Fix attempt executed (action: ${fix.fix_action as string})`,
        })
      }
    }

    if (incident.resolved_at) {
      timeline.push({
        timestamp: incident.resolved_at,
        event: 'resolved',
        detail: 'Incident resolved',
      })
    }

    timeline.sort((a, b) => {
      const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0
      const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0
      return ta - tb
    })

    res.json(toCamel({
      ...incident,
      fix_executions: fixesRes.rows,
      timeline,
    }))
  } catch (err) {
    next(err)
  }
})

export default router
