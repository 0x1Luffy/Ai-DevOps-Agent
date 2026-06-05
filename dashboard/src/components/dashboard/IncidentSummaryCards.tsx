import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import type { Incident } from '../../types'
import { ConfidenceMeter } from '../shared/ConfidenceMeter'
import { EmptyState } from '../shared/EmptyState'
import { AlertTriangle } from 'lucide-react'

const severityStyles: Record<string, string> = {
  CRITICAL: 'bg-red-500/15 text-red-400 border-red-500/30',
  HIGH: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  MEDIUM: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  LOW: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
}

interface IncidentSummaryCardsProps {
  incidents: Incident[]
  loading?: boolean
}

export function IncidentSummaryCards({ incidents, loading = false }: IncidentSummaryCardsProps) {
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 bg-gray-800/50 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (!incidents.length) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="No open incidents"
        message="All systems are operating normally."
      />
    )
  }

  return (
    <div className="space-y-2">
      {incidents.slice(0, 5).map((incident) => (
        <button
          key={incident.id}
          onClick={() => navigate(`/incidents/${incident.id}`)}
          className="w-full text-left bg-gray-800/60 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-lg px-4 py-3 transition-colors group"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={clsx(
                    'text-xs font-medium px-1.5 py-0.5 rounded border',
                    severityStyles[incident.severity],
                  )}
                >
                  {incident.severity}
                </span>
                <span className="text-gray-300 text-sm font-medium truncate">
                  {incident.resourceName}
                </span>
              </div>
              <p className="text-gray-500 text-xs truncate">{incident.problemType}</p>
            </div>
            <div className="shrink-0 flex flex-col items-end gap-1">
              <span className="text-gray-600 text-xs tabular-nums">
                {formatDistanceToNow(new Date(incident.detectedAt), { addSuffix: true })}
              </span>
              {incident.confidence !== null && (
                <div className="w-20">
                  <ConfidenceMeter value={incident.confidence} compact />
                </div>
              )}
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
