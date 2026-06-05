import clsx from 'clsx'
import type { NodeInfo } from '../../types'
import { ResourceUsageBar } from './ResourceUsageBar'
import { EmptyState } from '../shared/EmptyState'
import { Server, AlertTriangle } from 'lucide-react'

function parseCpu(raw: string): number {
  if (raw.endsWith('m')) return parseInt(raw) / 1000
  return parseFloat(raw) || 0
}

function parseMem(raw: string): number {
  if (raw.endsWith('Ki')) return parseInt(raw) / 1024
  if (raw.endsWith('Mi')) return parseInt(raw)
  if (raw.endsWith('Gi')) return parseFloat(raw) * 1024
  return parseFloat(raw) || 0
}

interface NodeCardProps {
  node: NodeInfo
}

function NodeCard({ node }: NodeCardProps) {
  const isReady = node.status === 'Ready'
  const cpuUsed = parseCpu(node.cpuUsed)
  const cpuTotal = parseCpu(node.cpuAllocatable)
  const memUsed = parseMem(node.memoryUsed)
  const memTotal = parseMem(node.memoryAllocatable)

  const abnormalConditions = node.conditions.filter(
    (c) => c.type !== 'Ready' && c.status === 'True',
  )

  return (
    <div
      className={clsx(
        'bg-gray-800/60 border rounded-xl p-4 space-y-4',
        isReady ? 'border-gray-700/60' : 'border-red-500/40',
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className={clsx(
              'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
              isReady ? 'bg-green-500/15' : 'bg-red-500/15',
            )}
          >
            <Server size={14} className={isReady ? 'text-green-400' : 'text-red-400'} />
          </div>
          <div className="min-w-0">
            <p className="text-gray-200 text-sm font-medium truncate">{node.name}</p>
            <p className="text-gray-500 text-xs">{node.role}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span
            className={clsx(
              'text-xs font-medium px-2 py-0.5 rounded-full',
              isReady ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400',
            )}
          >
            {node.status}
          </span>
        </div>
      </div>

      {/* Resource usage */}
      <div className="space-y-3">
        <ResourceUsageBar
          label="CPU"
          used={cpuUsed}
          total={cpuTotal}
          unit=" cores"
          formatValue={(v) => v.toFixed(2)}
        />
        <ResourceUsageBar
          label="Memory"
          used={memUsed}
          total={memTotal}
          unit=" Mi"
          formatValue={(v) => v.toFixed(0)}
        />
        <ResourceUsageBar
          label="Pods"
          used={node.podCount}
          total={node.podCapacity}
        />
      </div>

      {/* Warning conditions */}
      {abnormalConditions.length > 0 && (
        <div className="space-y-1">
          {abnormalConditions.map((cond) => (
            <div
              key={cond.type}
              className="flex items-center gap-1.5 text-xs text-yellow-400 bg-yellow-500/10 rounded px-2 py-1"
            >
              <AlertTriangle size={10} />
              {cond.type}
              {cond.reason && `: ${cond.reason}`}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface NodeGridProps {
  nodes: NodeInfo[]
  loading?: boolean
}

export function NodeGrid({ nodes, loading = false }: NodeGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-52 bg-gray-800/50 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  if (!nodes.length) {
    return (
      <EmptyState
        icon={Server}
        title="No nodes found"
        message="Could not retrieve cluster node information."
      />
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {nodes.map((node) => (
        <NodeCard key={node.name} node={node} />
      ))}
    </div>
  )
}
