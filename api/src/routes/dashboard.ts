import { Router, Request, Response, NextFunction } from 'express'
import axios from 'axios'
import { query } from '../db/client'
import { config } from '../config'
import { toCamel, ratio } from '../utils/shape'

const router = Router()

function agentHeaders() {
  return { 'X-API-Key': config.apiKey }
}

interface ActivityEvent {
  id: string
  type: 'incident' | 'fix'
  timestamp: Date
  description: string
  severity?: string
  result?: string
  namespace?: string
}

// GET /api/dashboard/summary
router.get('/summary', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const now = new Date()
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

    // All queries run in parallel
    const [
      clusterHealthResult,
      openCountRes,
      criticalCountRes,
      fixedLast24hRes,
      fixSuccessRateRes,
      activeApprovalsRes,
      jenkinsFailures24hRes,
      topProblemsRes,
      recentIncidentsRes,
      recentFixesRes,
      incidentTrendRes,
    ] = await Promise.allSettled([
      // Cluster health from agent
      axios.get(`${config.agentUrl}/cluster/health-gate`, { timeout: 5000, headers: agentHeaders() }).catch(() => null),
      // Open incidents count
      query<{ count: string }>(
        "SELECT COUNT(*) as count FROM incidents WHERE status IN ('open', 'fixing')"
      ),
      // Critical open incidents
      query<{ count: string }>(
        "SELECT COUNT(*) as count FROM incidents WHERE severity = 'CRITICAL' AND status IN ('open', 'fixing')"
      ),
      // Fixed in last 24h
      query<{ count: string }>(
        "SELECT COUNT(*) as count FROM incidents WHERE status = 'fixed' AND resolved_at >= $1",
        [yesterday.toISOString()]
      ),
      // Fix success rate last 7 days
      query<{ success: string; total: string }>(
        `SELECT
           COUNT(*) FILTER (WHERE result = 'success') as success,
           COUNT(*) as total
         FROM fix_executions
         WHERE executed_at >= $1`,
        [sevenDaysAgo.toISOString()]
      ),
      // Active approvals
      query<{ count: string }>(
        "SELECT COUNT(*) as count FROM incidents WHERE status = 'needs_approval'"
      ),
      // Jenkins failures in last 24h
      query<{ count: string }>(
        "SELECT COUNT(*) as count FROM jenkins_incidents WHERE detected_at >= $1",
        [yesterday.toISOString()]
      ),
      // Top 5 problem types last 24h
      query<{ problem_type: string; count: string }>(
        `SELECT problem_type, COUNT(*) as count
         FROM incidents
         WHERE detected_at >= $1
         GROUP BY problem_type
         ORDER BY count DESC
         LIMIT 5`,
        [yesterday.toISOString()]
      ),
      // Recent incidents (last 10)
      query<{
        id: string
        detected_at: Date
        problem_type: string
        severity: string
        namespace: string
        resource_name: string
      }>(
        `SELECT id, detected_at, problem_type, severity, namespace, resource_name
         FROM incidents
         ORDER BY detected_at DESC
         LIMIT 10`
      ),
      // Recent fixes (last 10)
      query<{
        id: string
        executed_at: Date
        result: string
        incident_id: string
        fix_action: string
      }>(
        `SELECT id, executed_at, result, incident_id, fix_action
         FROM fix_executions
         ORDER BY executed_at DESC
         LIMIT 10`
      ),
      // Incident trend last 7 days
      query<{ date: string; count: string }>(
        `SELECT
           DATE(detected_at) as date,
           COUNT(*) as count
         FROM incidents
         WHERE detected_at >= $1
         GROUP BY DATE(detected_at)
         ORDER BY date ASC`,
        [sevenDaysAgo.toISOString()]
      ),
    ])

    // Extract values safely from settled promises
    const clusterHealthData =
      clusterHealthResult.status === 'fulfilled' && clusterHealthResult.value
      ? (clusterHealthResult.value as { data: { score?: number; status?: string } }).data
      : null

    const clusterHealthScore = clusterHealthData?.score ?? 0
    const clusterStatus = clusterHealthData?.status ?? 'unknown'

    const openIncidents =
      openCountRes.status === 'fulfilled'
        ? parseInt(openCountRes.value.rows[0]?.count ?? '0', 10)
        : 0

    const criticalIncidents =
      criticalCountRes.status === 'fulfilled'
        ? parseInt(criticalCountRes.value.rows[0]?.count ?? '0', 10)
        : 0

    const fixedLast24h =
      fixedLast24hRes.status === 'fulfilled'
        ? parseInt(fixedLast24hRes.value.rows[0]?.count ?? '0', 10)
        : 0

    let fixSuccessRate = 0
    if (fixSuccessRateRes.status === 'fulfilled') {
      const row = fixSuccessRateRes.value.rows[0]
      const total = parseInt(row?.total ?? '0', 10)
      const success = parseInt(row?.success ?? '0', 10)
      fixSuccessRate = ratio(success, total)
    }

    const activeApprovals =
      activeApprovalsRes.status === 'fulfilled'
        ? parseInt(activeApprovalsRes.value.rows[0]?.count ?? '0', 10)
        : 0

    const jenkinsFailures24h =
      jenkinsFailures24hRes.status === 'fulfilled'
        ? parseInt(jenkinsFailures24hRes.value.rows[0]?.count ?? '0', 10)
        : 0

    const topProblems =
      topProblemsRes.status === 'fulfilled'
        ? topProblemsRes.value.rows.map((r) => ({
            type: r.problem_type,
            count: parseInt(r.count, 10),
          }))
        : []

    // Build recent activity from incidents and fixes combined
    const recentActivity: ActivityEvent[] = []

    if (recentIncidentsRes.status === 'fulfilled') {
      for (const row of recentIncidentsRes.value.rows) {
        recentActivity.push({
          id: row.id,
          type: 'incident',
          timestamp: row.detected_at,
          description: `${row.problem_type} detected in ${row.namespace}/${row.resource_name}`,
          severity: row.severity,
          namespace: row.namespace,
        })
      }
    }

    if (recentFixesRes.status === 'fulfilled') {
      for (const row of recentFixesRes.value.rows) {
        recentActivity.push({
          id: row.id,
          type: 'fix',
          timestamp: row.executed_at,
          description: `Fix (${row.fix_action}) ${row.result === 'success' ? 'succeeded' : row.result === 'failed' ? 'failed' : 'started'} for incident ${row.incident_id}`,
          result: row.result,
        })
      }
    }

    recentActivity.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    const top10Activity = recentActivity.slice(0, 10)

    const incidentTrend =
      incidentTrendRes.status === 'fulfilled'
        ? incidentTrendRes.value.rows.map((r) => ({
            date: r.date,
            count: parseInt(r.count, 10),
          }))
        : []

    res.json({
      clusterHealthScore,
      clusterStatus,
      openIncidents,
      criticalIncidents,
      fixedLast24h,
      fixSuccessRate,
      activeApprovals,
      jenkinsFailures24h,
      topProblems,
      recentActivity: top10Activity,
      incidentTrend,
    })
  } catch (err) {
    next(err)
  }
})

export default router
