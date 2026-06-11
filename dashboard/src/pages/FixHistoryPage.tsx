import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { History, Zap, TrendingUp } from 'lucide-react'
import { format, subDays } from 'date-fns'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { fetchFixes, fetchFixPatterns, fetchMetricsTrends } from '../api/client'
import { FixHistoryTable } from '../components/fixes/FixHistoryTable'
import { EmptyState } from '../components/shared/EmptyState'

interface TrendData {
  date: string
  successRate: number
  count: number
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ value: number; name: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-green-400">{p.name}: {p.value.toFixed(1)}%</p>
      ))}
    </div>
  )
}

export function FixHistoryPage() {
  const [fixFilters, setFixFilters] = useState({ page: 1, limit: 20 })

  const { data: fixesData, isLoading: fixesLoading } = useQuery({
    queryKey: ['fixes', fixFilters],
    queryFn: () => fetchFixes(fixFilters as Record<string, unknown>).then((r) => r.data),
    staleTime: 15_000,
  })

  const { data: patterns, isLoading: patternsLoading } = useQuery({
    queryKey: ['fix-patterns'],
    queryFn: () => fetchFixPatterns().then((r) => r.data),
    staleTime: 60_000,
  })

  const { data: trendsData } = useQuery({
    queryKey: ['metrics-trends', 30],
    queryFn: () => fetchMetricsTrends(30).then((r) => r.data),
    staleTime: 60_000,
  })

  // Build trend chart data — use API data or generate placeholder
  const chartData: TrendData[] = Array.isArray((trendsData as { fixSuccessByDay?: TrendData[] } | undefined)?.fixSuccessByDay)
    ? (trendsData as { fixSuccessByDay: TrendData[] }).fixSuccessByDay
    : Array.from({ length: 30 }, (_, i) => ({
        date: format(subDays(new Date(), 29 - i), 'MMM d'),
        successRate: 0,
        count: 0,
      }))

  const overallSuccessRate = fixesData?.successRate ?? 0

  return (
    <div className="space-y-6 max-w-screen-xl">
      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <p className="text-gray-500 text-sm">Total Fixes</p>
          <p className="text-3xl font-bold text-white mt-1 tabular-nums">
            {fixesData?.total ?? 0}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <p className="text-gray-500 text-sm">Overall Success Rate</p>
          <p className="text-3xl font-bold text-green-400 mt-1 tabular-nums">
            {(overallSuccessRate * 100).toFixed(1)}%
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <p className="text-gray-500 text-sm">Fix Patterns</p>
          <p className="text-3xl font-bold text-indigo-400 mt-1 tabular-nums">
            {patterns?.length ?? 0}
          </p>
        </div>
      </div>

      {/* Success Rate Trend */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <TrendingUp size={16} className="text-green-400" />
          <h2 className="text-gray-200 font-semibold">Fix Success Rate — Last 30 Days</h2>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="date"
              tick={{ fill: '#6b7280', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: '#6b7280', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="successRate"
              name="Success Rate"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#22c55e' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Fix Patterns table */}
      {(patterns?.length ?? 0) > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <Zap size={16} className="text-yellow-400" />
            <h2 className="text-gray-200 font-semibold">Fix Patterns</h2>
          </div>
          {patternsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-10 bg-gray-800/50 rounded animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-gray-400 font-medium px-4 py-3">Pattern</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">Fix Action</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3 tabular-nums">Success</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3 tabular-nums">Failure</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">Rate</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">Last Used</th>
                  </tr>
                </thead>
                <tbody>
                  {patterns?.map((p) => (
                    <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors">
                      <td className="px-4 py-3 text-gray-300 max-w-xs truncate">{p.problemPattern}</td>
                      <td className="px-4 py-3 text-gray-400 max-w-xs truncate">{p.fixAction}</td>
                      <td className="px-4 py-3 text-green-400 tabular-nums">{p.successCount}</td>
                      <td className="px-4 py-3 text-red-400 tabular-nums">{p.failureCount}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-green-500 rounded-full"
                              style={{ width: `${p.successRate * 100}%` }}
                            />
                          </div>
                          <span className="text-gray-400 text-xs tabular-nums">
                            {(p.successRate * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-600 text-xs">
                        {p.lastUsed ? format(new Date(p.lastUsed), 'MMM d, HH:mm') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Fix execution history */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <History size={16} className="text-indigo-400" />
          <h2 className="text-gray-200 font-semibold">Fix Execution History</h2>
          {fixesData && (
            <span className="ml-auto text-gray-600 text-xs">{fixesData.total} total</span>
          )}
        </div>
        <FixHistoryTable
          executions={fixesData?.fixes ?? []}
          loading={fixesLoading}
        />

        {/* Pagination */}
        {!fixesLoading && fixesData && fixesData.total > fixFilters.limit && (
          <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-gray-800">
            <button
              onClick={() => setFixFilters((p) => ({ ...p, page: Math.max(1, p.page - 1) }))}
              disabled={fixFilters.page === 1}
              className="text-xs text-gray-400 hover:text-gray-200 disabled:opacity-30 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
            >
              Previous
            </button>
            <span className="text-gray-500 text-xs">Page {fixFilters.page}</span>
            <button
              onClick={() => setFixFilters((p) => ({ ...p, page: p.page + 1 }))}
              disabled={fixesData.fixes.length < fixFilters.limit}
              className="text-xs text-gray-400 hover:text-gray-200 disabled:opacity-30 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
