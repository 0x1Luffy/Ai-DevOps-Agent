import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { ExternalLink } from 'lucide-react'
import type { Incident } from '../../types'
import { SeverityBadge } from './SeverityBadge'
import { ConfidenceMeter } from '../shared/ConfidenceMeter'
import { EmptyState } from '../shared/EmptyState'
import { AlertTriangle } from 'lucide-react'

const statusStyles: Record<string, string> = {
  open: 'bg-gray-700 text-gray-300',
  diagnosing: 'bg-blue-500/15 text-blue-400',
  needs_approval: 'bg-cyan-500/15 text-cyan-400',
  fixing: 'bg-yellow-500/15 text-yellow-400',
  fixed: 'bg-green-500/15 text-green-400',
  still_broken: 'bg-red-500/15 text-red-400',
  escalated: 'bg-orange-500/15 text-orange-400',
  manual: 'bg-purple-500/15 text-purple-400',
  skipped: 'bg-gray-600/20 text-gray-500',
}

interface IncidentTableProps {
  incidents: Incident[]
  loading?: boolean
  onSelect: (incident: Incident) => void
}

export function IncidentTable({ incidents, loading = false, onSelect }: IncidentTableProps) {
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
        icon={AlertTriangle}
        title="No incidents found"
        message="Try adjusting your filters or wait for new incidents to be detected."
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Severity</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Resource</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Namespace</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Problem Type</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Detected</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Status</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap w-32">Confidence</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3 whitespace-nowrap">Actions</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((incident) => (
            <tr
              key={incident.id}
              className="border-b border-gray-800 hover:bg-gray-800/40 transition-colors"
            >
              <td className="px-4 py-3">
                <SeverityBadge severity={incident.severity} size="sm" />
              </td>
              <td className="px-4 py-3">
                <span className="text-gray-200 font-medium">{incident.resourceName}</span>
                <p className="text-gray-600 text-xs">{incident.resourceType}</p>
              </td>
              <td className="px-4 py-3">
                <span className="text-gray-400 font-mono text-xs bg-gray-800 px-1.5 py-0.5 rounded">
                  {incident.namespace}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-400 max-w-xs truncate">{incident.problemType}</td>
              <td className="px-4 py-3 text-gray-500 text-xs tabular-nums whitespace-nowrap">
                {formatDistanceToNow(new Date(incident.detectedAt), { addSuffix: true })}
              </td>
              <td className="px-4 py-3">
                <span
                  className={clsx(
                    'text-xs font-medium px-2 py-0.5 rounded-full',
                    statusStyles[incident.status] ?? statusStyles.open,
                  )}
                >
                  {incident.status.replace('_', ' ')}
                </span>
              </td>
              <td className="px-4 py-3">
                <ConfidenceMeter value={incident.confidence} compact />
              </td>
              <td className="px-4 py-3">
                <button
                  onClick={() => onSelect(incident)}
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
                >
                  <ExternalLink size={12} />
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
