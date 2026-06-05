import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { GitBranch } from 'lucide-react'
import type { JenkinsIncident } from '../../types'
import { EmptyState } from '../shared/EmptyState'
import { FailureClassificationBadge } from './FailureClassificationBadge'
import type { JenkinsFailureType } from '../../types'

interface BuildHistoryProps {
  incidents: JenkinsIncident[]
  loading?: boolean
}

export function BuildHistory({ incidents, loading = false }: BuildHistoryProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 bg-gray-800/50 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  if (!incidents.length) {
    return (
      <EmptyState
        icon={GitBranch}
        title="No build failures"
        message="No Jenkins build failures recorded."
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Build #</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Job</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Branch</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Status</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Duration</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Failure Type</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Action Taken</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Time</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => (
            <tr key={inc.id} className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors">
              <td className="px-4 py-3">
                <span className="text-gray-400 font-mono text-xs">
                  #{inc.buildNumber ?? '—'}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-300 max-w-xs truncate">{inc.jobName}</td>
              <td className="px-4 py-3">
                {inc.branch ? (
                  <span className="flex items-center gap-1 text-gray-500 text-xs">
                    <GitBranch size={10} />
                    {inc.branch}
                  </span>
                ) : (
                  <span className="text-gray-700">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                <span
                  className={clsx(
                    'text-xs font-medium px-2 py-0.5 rounded-full',
                    inc.resolved
                      ? 'bg-green-500/15 text-green-400'
                      : 'bg-red-500/15 text-red-400',
                  )}
                >
                  {inc.resolved ? 'Resolved' : 'Failed'}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs tabular-nums">
                {inc.buildDurationSeconds !== null
                  ? `${Math.round(inc.buildDurationSeconds)}s`
                  : '—'}
              </td>
              <td className="px-4 py-3">
                {inc.failureType ? (
                  <FailureClassificationBadge failureType={inc.failureType as JenkinsFailureType} />
                ) : (
                  <span className="text-gray-700 text-xs">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs max-w-xs truncate">
                {inc.actionTaken ?? '—'}
              </td>
              <td className="px-4 py-3 text-gray-600 text-xs tabular-nums whitespace-nowrap">
                {formatDistanceToNow(new Date(inc.detectedAt), { addSuffix: true })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
