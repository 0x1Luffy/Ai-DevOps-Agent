import { Router, Request, Response, NextFunction } from 'express'
import { z } from 'zod'
import { query } from '../db/client'
import { createError } from '../middleware/errorHandler'
import { toCamel } from '../utils/shape'

const router = Router()

const ListQuerySchema = z.object({
  job_name: z.string().optional(),
  resolved: z.enum(['true', 'false']).optional(),
  from_date: z.string().datetime({ offset: true }).optional(),
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().positive().max(100).default(20),
})

// GET /api/jenkins/incidents
router.get('/incidents', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const parsed = ListQuerySchema.safeParse(req.query)
    if (!parsed.success) {
      return next(createError(parsed.error.errors[0]?.message ?? 'Invalid query params', 400, 'VALIDATION_ERROR'))
    }
    const { job_name, resolved, from_date, page, limit } = parsed.data

    const conditions: string[] = []
    const params: unknown[] = []
    let idx = 1

    if (job_name) {
      conditions.push(`job_name = $${idx++}`)
      params.push(job_name)
    }
    if (resolved !== undefined) {
      if (resolved === 'true') {
        conditions.push(`resolved_at IS NOT NULL`)
      } else {
        conditions.push(`resolved_at IS NULL`)
      }
    }
    if (from_date) {
      conditions.push(`detected_at >= $${idx++}`)
      params.push(from_date)
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

    const countResult = await query<{ count: string }>(
      `SELECT COUNT(*) as count FROM jenkins_incidents ${whereClause}`,
      params
    )
    const total = parseInt(countResult.rows[0]?.count ?? '0', 10)
    const offset = (page - 1) * limit

    const dataResult = await query(
      `SELECT * FROM jenkins_incidents ${whereClause}
       ORDER BY detected_at DESC
       LIMIT $${idx++} OFFSET $${idx++}`,
      [...params, limit, offset]
    )

    // Compute failures by type
    const failuresByTypeRes = await query<{ failure_type: string; count: string }>(
      `SELECT failure_type, COUNT(*) as count FROM jenkins_incidents ${whereClause} GROUP BY failure_type ORDER BY count DESC`,
      params
    )

    const failuresByType: Record<string, number> = {}
    for (const row of failuresByTypeRes.rows) {
      if (row.failure_type) {
        failuresByType[row.failure_type] = parseInt(row.count, 10)
      }
    }

    res.json({
      incidents: toCamel(dataResult.rows),
      total,
      failuresByType,
    })
  } catch (err) {
    next(err)
  }
})

// GET /api/jenkins/pipeline-health
router.get('/pipeline-health', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const result = await query<{
      job_name: string
      total_builds: string
      successful_builds: string
      last_build_at: Date | null
      common_failure_type: string | null
      avg_duration_seconds: string | null
    }>(
      `SELECT
         job_name,
         COUNT(*) AS total_builds,
         COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) AS successful_builds,
         MAX(detected_at) AS last_build_at,
         MODE() WITHIN GROUP (ORDER BY failure_type) AS common_failure_type,
         AVG(build_duration_seconds) AS avg_duration_seconds
       FROM jenkins_incidents
       GROUP BY job_name
       ORDER BY total_builds DESC`
    )

    const jobs = result.rows.map((row) => {
      const total = parseInt(row.total_builds, 10)
      const successful = parseInt(row.successful_builds, 10)
      const successRate = total > 0 ? parseFloat(((successful / total) * 100).toFixed(2)) : 0
      const avgDuration = row.avg_duration_seconds
        ? parseFloat(parseFloat(row.avg_duration_seconds).toFixed(2))
        : null

      return {
        name: row.job_name,
        successRate,
        lastBuild: row.last_build_at,
        totalBuilds: total,
        commonFailureType: row.common_failure_type,
        avgDurationSeconds: avgDuration,
      }
    })

    res.json({ jobs })
  } catch (err) {
    next(err)
  }
})

export default router
