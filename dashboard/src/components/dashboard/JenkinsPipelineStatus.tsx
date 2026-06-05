import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import type { JenkinsIncident } from '../../types'
import { EmptyState } from '../shared/EmptyState'
import { GitBranch } from 'lucide-react'
import { FailureClassificationBadge } from '../jenkins/FailureClassificationBadge'

interface JenkinsPipelineStatusProps {
  incidents: JenkinsIncident[]
  loading?: boolean
}

export function JenkinsPipelineStatus({ incidents, loading = false }: JenkinsPipelineStatusProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 bg-gray-800/50 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (!incidents.length) {
    return (
      <EmptyState
        icon={GitBranch}
        title="No recent failures"
        message="All Jenkins pipelines are running successfully."
      />
    )
  }

  return (
    <div className="space-y-2">
      {incidents.slice(0, 5).map((incident) => (
        <div
          key={incident.id}
          className="bg-gray-800/60 border border-gray-700/50 rounded-lg px-4 py-3"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={clsx(
                    'text-xs font-medium px-1.5 py-0.5 rounded border',
                    incident.resolved
                      ? 'bg-green-500/10 text-green-400 border-green-500/30'
                      : 'bg-red-500/10 text-red-400 border-red-500/30',
                  )}
                >
                  {incident.resolved ? 'RESOLVED' : 'FAILED'}
                </span>
                <span className="text-gray-300 text-sm font-medium truncate">
                  {incident.jobName}
                </span>
                {incident.buildNumber && (
                  <span className="text-gray-600 text-xs">#{incident.buildNumber}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {incident.branch && (
                  <span className="text-gray-500 text-xs flex items-center gap-1">
                    <GitBranch size={10} />
                    {incident.branch}
                  </span>
                )}
                {incident.failureType && (
                  <FailureClassificationBadge failureType={incident.failureType} />
                )}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-gray-600 text-xs tabular-nums">
                {formatDistanceToNow(new Date(incident.detectedAt), { addSuffix: true })}
              </p>
              {incident.buildDurationSeconds !== null && (
                <p className="text-gray-700 text-xs mt-0.5">
                  {Math.round(incident.buildDurationSeconds)}s
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
