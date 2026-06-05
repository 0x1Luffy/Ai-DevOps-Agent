import { useEffect } from 'react'
import { type LucideIcon, AlertTriangle, CheckCircle, Clock, GitBranch } from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { useWebSocket } from '../hooks/useWebSocket'
import { useIncidents } from '../hooks/useIncidents'
import { useQuery } from '@tanstack/react-query'
import { fetchJenkinsIncidents } from '../api/client'
import { ClusterHealthScore } from '../components/dashboard/ClusterHealthScore'
import { IncidentSummaryCards } from '../components/dashboard/IncidentSummaryCards'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'
import { JenkinsPipelineStatus } from '../components/dashboard/JenkinsPipelineStatus'

interface StatCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  color: string
  sub?: string
  loading?: boolean
}

function StatCard({ title, value, icon: Icon, color, sub, loading = false }: StatCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-start justify-between">
      <div>
        <p className="text-gray-500 text-sm font-medium">{title}</p>
        {loading ? (
          <div className="h-8 w-16 bg-gray-800 rounded animate-pulse mt-2" />
        ) : (
          <p className={`text-3xl font-bold mt-1 tabular-nums ${color}`}>{value}</p>
        )}
        {sub && <p className="text-gray-600 text-xs mt-1">{sub}</p>}
      </div>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color.replace('text-', 'bg-').replace('400', '500/15')}`}>
        <Icon size={18} className={color} />
      </div>
    </div>
  )
}

export function DashboardPage() {
  useWebSocket()

  const { data: summary, isLoading: summaryLoading, error: summaryError } = useDashboard()
  const { data: incidentsData, isLoading: incidentsLoading } = useIncidents({
    status: 'open',
    limit: 5,
  })
  const { data: jenkinsData, isLoading: jenkinsLoading } = useQuery({
    queryKey: ['jenkins-incidents-recent'],
    queryFn: () => fetchJenkinsIncidents({ limit: 5 }).then((r) => r.data),
    refetchInterval: 30_000,
  })

  if (summaryError) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertTriangle size={32} className="text-red-400 mx-auto mb-3" />
          <p className="text-gray-400">Failed to load dashboard data.</p>
          <p className="text-gray-600 text-sm mt-1">Check that the API server is running.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-screen-xl">
      {/* Stat cards row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* Cluster Health */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col items-center justify-center">
          <p className="text-gray-500 text-sm font-medium mb-3 self-start">Cluster Health</p>
          <ClusterHealthScore
            score={summary?.clusterHealthScore ?? 0}
            status={summary?.clusterStatus ?? 'UNHEALTHY'}
            loading={summaryLoading}
          />
        </div>

        <StatCard
          title="Open Incidents"
          value={summary?.openIncidents ?? 0}
          icon={AlertTriangle}
          color="text-orange-400"
          sub={`${summary?.criticalIncidents ?? 0} critical`}
          loading={summaryLoading}
        />

        <StatCard
          title="Fixed Last 24h"
          value={summary?.fixedLast24h ?? 0}
          icon={CheckCircle}
          color="text-green-400"
          sub={`${((summary?.fixSuccessRate ?? 0) * 100).toFixed(0)}% success rate`}
          loading={summaryLoading}
        />

        <StatCard
          title="Pending Approvals"
          value={summary?.activeApprovals ?? 0}
          icon={Clock}
          color="text-cyan-400"
          sub={`${summary?.jenkinsFailures24h ?? 0} Jenkins failures today`}
          loading={summaryLoading}
        />
      </div>

      {/* Middle row: Incidents + Jenkins */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Recent Open Incidents */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-gray-200 font-semibold">Recent Open Incidents</h2>
            <span className="text-gray-600 text-xs">last 5</span>
          </div>
          <IncidentSummaryCards
            incidents={incidentsData?.incidents ?? []}
            loading={incidentsLoading}
          />
        </div>

        {/* Jenkins Pipeline Failures */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-gray-200 font-semibold">Jenkins Pipeline Failures</h2>
            <span className="text-gray-600 text-xs">last 5</span>
          </div>
          <JenkinsPipelineStatus
            incidents={jenkinsData?.incidents ?? []}
            loading={jenkinsLoading}
          />
        </div>
      </div>

      {/* Activity Feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-gray-200 font-semibold">Live Activity Feed</h2>
          <span className="text-gray-600 text-xs">real-time via WebSocket</span>
        </div>
        <ActivityFeed />
      </div>
    </div>
  )
}
