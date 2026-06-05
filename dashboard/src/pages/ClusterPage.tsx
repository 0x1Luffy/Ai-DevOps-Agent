import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, Server, Layers } from 'lucide-react'
import clsx from 'clsx'
import { useClusterHealth, useNodes } from '../hooks/useClusterHealth'
import { fetchNamespaces } from '../api/client'
import { NodeGrid } from '../components/cluster/NodeGrid'
import { NamespaceHealth, type NamespaceHealthData } from '../components/cluster/NamespaceHealth'
import { PodStatusGrid, type PodInfo } from '../components/cluster/PodStatusGrid'
import type { ClusterHealth } from '../types'

function ClusterHealthCard({ health, loading }: { health: ClusterHealth | undefined; loading: boolean }) {
  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 animate-pulse">
        <div className="h-6 w-48 bg-gray-800 rounded mb-4" />
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 bg-gray-800/50 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (!health) return null

  const checkEntries = Object.entries(health.checks) as Array<
    [string, { score: number; details: string }]
  >

  return (
    <div
      className={clsx(
        'bg-gray-900 border rounded-xl p-6',
        health.status === 'HEALTHY' && 'border-green-500/30',
        health.status === 'DEGRADED' && 'border-yellow-500/30',
        health.status === 'UNHEALTHY' && 'border-red-500/30',
      )}
    >
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-gray-200 font-semibold text-lg">Cluster Health</h2>
          <p className="text-gray-500 text-sm mt-0.5">{health.recommendation}</p>
        </div>
        <div className="flex flex-col items-end">
          <span
            className={clsx(
              'text-2xl font-bold tabular-nums',
              health.score >= 80 ? 'text-green-400' : health.score >= 60 ? 'text-yellow-400' : 'text-red-400',
            )}
          >
            {Math.round(health.score)}
          </span>
          <span
            className={clsx(
              'text-xs font-medium px-2 py-0.5 rounded-full mt-1',
              health.status === 'HEALTHY' && 'bg-green-500/15 text-green-400',
              health.status === 'DEGRADED' && 'bg-yellow-500/15 text-yellow-400',
              health.status === 'UNHEALTHY' && 'bg-red-500/15 text-red-400',
            )}
          >
            {health.status}
          </span>
        </div>
      </div>

      {/* Checks */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
        {checkEntries.map(([key, check]) => (
          <div
            key={key}
            className="bg-gray-800/60 border border-gray-700/50 rounded-lg px-4 py-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400 text-xs font-medium capitalize">
                {key.replace(/([A-Z])/g, ' $1').trim()}
              </span>
              <span
                className={clsx(
                  'text-sm font-bold tabular-nums',
                  check.score >= 80 ? 'text-green-400' : check.score >= 60 ? 'text-yellow-400' : 'text-red-400',
                )}
              >
                {check.score}
              </span>
            </div>
            <p className="text-gray-600 text-xs leading-tight">{check.details}</p>
          </div>
        ))}
      </div>

      {/* Issues */}
      {health.issues.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-gray-500 text-xs font-medium uppercase tracking-wider">Active Issues</h3>
          {health.issues.map((issue, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
            >
              <AlertTriangle size={12} className="text-red-400 shrink-0 mt-0.5" />
              <div>
                <span className="text-red-300 text-xs font-medium">{issue.type}</span>
                <p className="text-red-400/70 text-xs">{issue.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ClusterPage() {
  const { data: health, isLoading: healthLoading } = useClusterHealth()
  const { data: nodes, isLoading: nodesLoading } = useNodes()
  const [selectedNamespace, setSelectedNamespace] = useState('all')

  // Build fake namespace health data from nodes/context (in a real app, this would come from the API)
  const namespaces: NamespaceHealthData[] = []

  // Empty pods array — would come from a real pods API endpoint
  const pods: PodInfo[] = []

  return (
    <div className="space-y-6 max-w-screen-xl">
      {/* Cluster health gate */}
      <ClusterHealthCard health={health} loading={healthLoading} />

      {/* Node Grid */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <Server size={16} className="text-indigo-400" />
          <h2 className="text-gray-200 font-semibold">Cluster Nodes</h2>
          {nodes && (
            <span className="text-gray-600 text-xs ml-auto">
              {nodes.filter((n) => n.status === 'Ready').length}/{nodes.length} Ready
            </span>
          )}
        </div>
        <NodeGrid nodes={nodes ?? []} loading={nodesLoading} />
      </div>

      {/* Namespace Health */}
      {namespaces.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <Layers size={16} className="text-cyan-400" />
            <h2 className="text-gray-200 font-semibold">Namespace Health</h2>
          </div>
          <NamespaceHealth namespaces={namespaces} />
        </div>
      )}

      {/* Pod Status Grid */}
      {pods.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <CheckCircle size={16} className="text-green-400" />
            <h2 className="text-gray-200 font-semibold">Pod Status</h2>
          </div>
          <PodStatusGrid
            pods={pods}
            selectedNamespace={selectedNamespace}
            onNamespaceChange={setSelectedNamespace}
          />
        </div>
      )}
    </div>
  )
}
