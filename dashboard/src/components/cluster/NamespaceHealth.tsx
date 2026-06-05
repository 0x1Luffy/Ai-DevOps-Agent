import clsx from 'clsx'
import { EmptyState } from '../shared/EmptyState'
import { Layers } from 'lucide-react'

export interface NamespaceHealthData {
  namespace: string
  openIncidents: number
  criticalCount: number
  quotaUsedPct: number | null
  status: 'healthy' | 'warning' | 'critical'
}

const statusStyles: Record<string, string> = {
  healthy: 'bg-green-500/15 text-green-400',
  warning: 'bg-yellow-500/15 text-yellow-400',
  critical: 'bg-red-500/15 text-red-400',
}

interface NamespaceHealthProps {
  namespaces: NamespaceHealthData[]
  loading?: boolean
}

export function NamespaceHealth({ namespaces, loading = false }: NamespaceHealthProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 bg-gray-800/50 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  if (!namespaces.length) {
    return (
      <EmptyState
        icon={Layers}
        title="No namespaces"
        message="No namespace health data available."
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-gray-400 font-medium px-4 py-3">Namespace</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3">Open Incidents</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3">Critical</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3">Quota Usage</th>
            <th className="text-left text-gray-400 font-medium px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {namespaces.map((ns) => (
            <tr key={ns.namespace} className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors">
              <td className="px-4 py-3">
                <span className="text-gray-200 font-mono text-xs bg-gray-800 px-2 py-1 rounded">
                  {ns.namespace}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-300 tabular-nums">{ns.openIncidents}</td>
              <td className="px-4 py-3">
                {ns.criticalCount > 0 ? (
                  <span className="text-red-400 font-semibold tabular-nums">{ns.criticalCount}</span>
                ) : (
                  <span className="text-gray-600">0</span>
                )}
              </td>
              <td className="px-4 py-3">
                {ns.quotaUsedPct !== null ? (
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={clsx(
                          'h-full rounded-full',
                          ns.quotaUsedPct >= 90
                            ? 'bg-red-500'
                            : ns.quotaUsedPct >= 75
                            ? 'bg-yellow-500'
                            : 'bg-green-500',
                        )}
                        style={{ width: `${ns.quotaUsedPct}%` }}
                      />
                    </div>
                    <span className="text-gray-500 text-xs tabular-nums">
                      {ns.quotaUsedPct.toFixed(0)}%
                    </span>
                  </div>
                ) : (
                  <span className="text-gray-600 text-xs">N/A</span>
                )}
              </td>
              <td className="px-4 py-3">
                <span
                  className={clsx(
                    'text-xs font-medium px-2 py-0.5 rounded-full capitalize',
                    statusStyles[ns.status],
                  )}
                >
                  {ns.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
