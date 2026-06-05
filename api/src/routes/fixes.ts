import { Router, Request, Response, NextFunction } from 'express'
import { z } from 'zod'
import { Redis } from 'ioredis'
import { query } from '../db/client'
import { createError } from '../middleware/errorHandler'

const router = Router()

// Redis client is injected via app.locals
function getRedis(req: Request): Redis {
  return req.app.locals.redis as Redis
}

const ListQuerySchema = z.object({
  result: z.enum(['success', 'failure', 'pending']).optional(),
  from_date: z.string().datetime({ offset: true }).optional(),
  to_date: z.string().datetime({ offset: true }).optional(),
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().positive().max(100).default(20),
})

const ApproveBodySchema = z.object({
  approver: z.string().min(1),
})

// GET /api/fixes
router.get('/', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const parsed = ListQuerySchema.safeParse(req.query)
    if (!parsed.success) {
      return next(createError(parsed.error.errors[0]?.message ?? 'Invalid query params', 400, 'VALIDATION_ERROR'))
    }
    const { result, from_date, to_date, page, limit } = parsed.data

    const conditions: string[] = []
    const params: unknown[] = []
    let idx = 1

    if (result) {
      conditions.push(`result = $${idx++}`)
      params.push(result)
    }
    if (from_date) {
      conditions.push(`started_at >= $${idx++}`)
      params.push(from_date)
    }
    if (to_date) {
      conditions.push(`started_at <= $${idx++}`)
      params.push(to_date)
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

    const countResult = await query<{ count: string }>(
      `SELECT COUNT(*) as count FROM fix_executions ${whereClause}`,
      params
    )
    const total = parseInt(countResult.rows[0]?.count ?? '0', 10)
    const offset = (page - 1) * limit

    const dataResult = await query(
      `SELECT fe.*, i.namespace, i.resource_name, i.problem_type, i.severity
       FROM fix_executions fe
       LEFT JOIN incidents i ON i.id = fe.incident_id
       ${whereClause}
       ORDER BY fe.started_at DESC
       LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, limit, offset]
    )

    // Compute success rate from all time (or filtered range)
    const successRateRes = await query<{ success: string; failure: string }>(
      `SELECT
         COUNT(*) FILTER (WHERE result = 'success') as success,
         COUNT(*) FILTER (WHERE result = 'failure') as failure
       FROM fix_executions ${whereClause}`,
      params
    )
    const successCount = parseInt(successRateRes.rows[0]?.success ?? '0', 10)
    const failureCount = parseInt(successRateRes.rows[0]?.failure ?? '0', 10)
    const denom = successCount + failureCount
    const successRate = denom > 0 ? parseFloat(((successCount / denom) * 100).toFixed(2)) : 0

    res.json({
      fixes: dataResult.rows,
      total,
      successRate,
    })
  } catch (err) {
    next(err)
  }
})

// GET /api/fixes/patterns
router.get('/patterns', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const result = await query(
      `SELECT
         id,
         problem_type,
         fix_strategy,
         fix_commands,
         success_count,
         failure_count,
         last_used_at,
         created_at,
         CASE
           WHEN (success_count + failure_count) = 0 THEN 0
           ELSE ROUND((success_count::numeric / (success_count + failure_count)) * 100, 2)
         END AS success_rate
       FROM fix_patterns
       ORDER BY (success_count + failure_count) DESC`
    )

    res.json(result.rows)
  } catch (err) {
    next(err)
  }
})

// POST /api/fixes/:incident_id/approve
router.post('/:incident_id/approve', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const { incident_id } = req.params

    const parsed = ApproveBodySchema.safeParse(req.body)
    if (!parsed.success) {
      return next(createError(parsed.error.errors[0]?.message ?? 'Invalid request body', 400, 'VALIDATION_ERROR'))
    }
    const { approver } = parsed.data

    // Verify incident exists and needs approval
    const incidentRes = await query<{ id: string; status: string }>(
      'SELECT id, status FROM incidents WHERE id = $1',
      [incident_id]
    )
    if (incidentRes.rows.length === 0) {
      return next(createError('Incident not found', 404, 'NOT_FOUND'))
    }
    const incident = incidentRes.rows[0]
    if (!incident) {
      return next(createError('Incident not found', 404, 'NOT_FOUND'))
    }
    if (incident.status !== 'needs_approval') {
      return next(createError(`Incident is not awaiting approval (current status: ${incident.status})`, 409, 'INVALID_STATE'))
    }

    const redis = getRedis(req)
    const payload = JSON.stringify({
      incident_id,
      approver,
      action: 'approve',
      approved_at: new Date().toISOString(),
    })

    await redis.publish('autopilot:approvals', payload)

    res.json({
      approved: true,
      message: 'Fix queued for execution',
    })
  } catch (err) {
    next(err)
  }
})

export default router
