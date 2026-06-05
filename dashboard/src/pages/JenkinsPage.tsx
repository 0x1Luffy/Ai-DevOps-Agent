import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GitBranch, RefreshCw, TrendingUp } from 'lucide-react'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { fetchJenkinsIncidents, fetchPipelineHealth } from '../api/client'
import { PipelineCard } from '../components/jenkins/PipelineCard'
import { BuildHistory } from '../components/jenkins/BuildHistory'
import { EmptyState } from '../components/shared/EmptyState'

const CHART_COLORS = [
  '#818cf8', '#34d399', '#fb923c', '#f472b6', '#60a5fa',
  '#a78bfa', '#facc15', '#2dd4bf', '#f87171', '#94a3b8',
]

interface ChartPayload {
  name: string
  value: number
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload: ChartPayload; value: number }>
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-300 font-medium">{payload[0].payload.name}</p>
      <p className="text-gray-400">{payload[0].value} failures</p>
    </div>
  )
}

export function JenkinsPage() {
  const [page, setPage] = useState(1)

  const { data: pipelineData, isLoading: pipelineLoading } = useQuery({
    queryKey: ['pipeline-health'],
    queryFn: () => fetchPipelineHealth().then((r) => r.data),
    refetchInterval: 60_000,
  })

  const { data: incidentsData, isLoading: incidentsLoading } = useQuery({
    queryKey: ['jenkins-incidents', page],
    queryFn: () => fetchJenkinsIncidents({ page, limit: 20 }).then((r) => r.data),
    refetchInterval: 30_000,
  })

  const failuresByType = incidentsData?.failuresByType ?? {}
  const pieData = Object.entries(failuresByType)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  const totalRetries = incidentsData?.incidents.reduce((sum, i) => sum + i.retryCount, 0) ?? 0
  const resolved = incidentsData?.incidents.filter((i) => i.resolved).length ?? 0
  const total = incidentsData?.incidents.length ?? 0

  return (
    <div className="space-y-6 max-w-screen-xl">
      {/* Pipeline Health Overview */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <TrendingUp size={16} className="text-indigo-400" />
          <h2 className="text-gray-200 font-semibold">Pipeline Health Overview</h2>
        </div>
        {pipelineLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-32 bg-gray-800/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : pipelineData?.jobs && pipelineData.jobs.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {pipelineData.jobs.map((job) => (
              <PipelineCard key={job.name} pipeline={job} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={GitBranch}
            title="No pipeline data"
            message="No Jenkins pipeline health data available."
          />
        )}
      </div>

      {/* Build History + Failure Distribution */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Build History table */}
        <div className="xl:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <GitBranch size={16} className="text-orange-400" />
            <h2 className="text-gray-200 font-semibold">Build Failure History</h2>
            {incidentsData && (
              <span className="ml-auto text-gray-600 text-xs">{incidentsData.total} total</span>
            )}
          </div>
          <BuildHistory
            incidents={incidentsData?.incidents ?? []}
            loading={incidentsLoading}
          />
          {!incidentsLoading && incidentsData && incidentsData.total > 20 && (
            <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-gray-800">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-xs text-gray-400 hover:text-gray-200 disabled:opacity-30 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
              >
                Previous
              </button>
              <span className="text-gray-500 text-xs">Page {page}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={incidentsData.incidents.length < 20}
                className="text-xs text-gray-400 hover:text-gray-200 disabled:opacity-30 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Auto-retry stats */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <RefreshCw size={14} className="text-cyan-400" />
              <h3 className="text-gray-200 font-semibold text-sm">Auto-Retry Stats</h3>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-500 text-sm">Total Retries</span>
                <span className="text-gray-200 font-semibold tabular-nums">{totalRetries}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500 text-sm">Resolved</span>
                <span className="text-green-400 font-semibold tabular-nums">{resolved}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500 text-sm">Still Failing</span>
                <span className="text-red-400 font-semibold tabular-nums">{total - resolved}</span>
              </div>
              {total > 0 && (
                <div className="pt-1">
                  <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                    <span>Resolution Rate</span>
                    <span>{((resolved / total) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full"
                      style={{ width: `${(resolved / total) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Failure distribution donut */}
          {pieData.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-gray-200 font-semibold text-sm mb-4">Failure Distribution</h3>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="45%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={CHART_COLORS[index % CHART_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    formatter={(value) => (
                      <span style={{ color: '#9ca3af', fontSize: '11px' }}>{value}</span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
