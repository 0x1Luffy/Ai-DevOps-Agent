import { format } from 'date-fns'
import clsx from 'clsx'
import type { FixExecution } from '../../types'
import { EmptyState } from '../shared/EmptyState'
import { History } from 'lucide-react'

const resultStyles: Record<string, string> = {
  success: 'bg-green-500/15 text-green-400',
  failed: 'bg-red-500/15 text-red-400',
  partial: 'bg-yellow-500/15 text-yellow-400',
  skipped: 'bg-gray-600/20 text-gray-500',
}

const verifyStyles: Record<string, string> = {
  fixed: 'bg-green-500/15 text-green-400',
  still_broken: 'bg-red-500/15 text-red-400',
  degraded: 'bg-orange-500/15 text-orange-400',
  pending: 'bg-blue-500/15 text-blue-400',
  skipped: 'bg-gray-600/20 text-gray-500',
}

interface FixHistoryTableProps {
  executions: FixExecution[]
  loading?: boolean
}

export function FixHistoryTable({ executions, loading = false }: FixHistoryTableProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 bg-gray-800/50 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  if (!executions.length) {
    return (
      <EmptyState
        icon={History}
        title="No fix history"
        message="Fix executions will appear here once the agent starts applying fixes."
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Time</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Incident</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Action</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Executed By</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Result</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Verified</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Duration</th>
          </tr>
        </thead>
        <tbody>
          {executions.map((exec) => (
            <tr key={exec.id} className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors">
              <td className="px-4 py-3 text-gray-500 text-xs tabular-nums whitespace-nowrap">
                {format(new Date(exec.executedAt), 'MMM d, HH:mm:ss')}
              </td>
              <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                {exec.incidentId.slice(0, 8)}…
              </td>
              <td className="px-4 py-3 text-gray-300 max-w-xs truncate">
                {exec.fixAction}
              </td>
              <td className="px-4 py-3 text-gray-400 text-xs">{exec.executedBy}</td>
              <td className="px-4 py-3">
                <span
                  className={clsx(
                    'text-xs font-medium px-2 py-0.5 rounded-full',
                    exec.result ? resultStyles[exec.result] : 'bg-gray-600/20 text-gray-500',
                  )}
                >
                  {exec.result ?? 'pending'}
                </span>
              </td>
              <td className="px-4 py-3">
                <span
                  className={clsx(
                    'text-xs font-medium px-2 py-0.5 rounded-full',
                    exec.verificationStatus
                      ? verifyStyles[exec.verificationStatus]
                      : 'bg-gray-600/20 text-gray-500',
                  )}
                >
                  {exec.verificationStatus ?? 'pending'}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs tabular-nums">
                {exec.executionDurationMs !== null
                  ? `${(exec.executionDurationMs / 1000).toFixed(1)}s`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
