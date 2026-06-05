import { useState } from 'react'
import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import { X, Copy, RefreshCw } from 'lucide-react'
import { EmptyState } from '../shared/EmptyState'
import { Layers } from 'lucide-react'
import { CopyButton } from '../shared/CopyButton'

export interface PodInfo {
  name: string
  namespace: string
  phase: 'Running' | 'Pending' | 'Terminating' | 'Failed' | 'Succeeded'
  ready: boolean
  restartCount: number
  startedAt: string | null
  conditions: { type: string; status: string }[]
  logs?: string
  isCrashLoop?: boolean
}

type PodStatus = 'running-ready' | 'running-not-ready' | 'crashloop' | 'pending' | 'terminating' | 'other'

function getPodStatus(pod: PodInfo): PodStatus {
  if (pod.isCrashLoop) return 'crashloop'
  if (pod.phase === 'Running' && pod.ready) return 'running-ready'
  if (pod.phase === 'Running' && !pod.ready) return 'running-not-ready'
  if (pod.phase === 'Pending') return 'pending'
  if (pod.phase === 'Terminating') return 'terminating'
  return 'other'
}

const statusConfig: Record<PodStatus, { label: string; dot: string; card: string }> = {
  'running-ready': {
    label: 'Running',
    dot: 'bg-green-500',
    card: 'border-green-500/20 bg-green-500/5',
  },
  'running-not-ready': {
    label: 'Not Ready',
    dot: 'bg-orange-500',
    card: 'border-orange-500/20 bg-orange-500/5',
  },
  'crashloop': {
    label: 'CrashLoop',
    dot: 'bg-red-500',
    card: 'border-red-500/30 bg-red-500/10',
  },
  'pending': {
    label: 'Pending',
    dot: 'bg-yellow-500',
    card: 'border-yellow-500/20 bg-yellow-500/5',
  },
  'terminating': {
    label: 'Terminating',
    dot: 'bg-gray-500',
    card: 'border-gray-600/20 bg-gray-700/20',
  },
  'other': {
    label: 'Unknown',
    dot: 'bg-gray-600',
    card: 'border-gray-700/20',
  },
}

interface LogsModalProps {
  pod: PodInfo
  onClose: () => void
}

function LogsModal({ pod, onClose }: LogsModalProps) {
  const logs = pod.logs ?? '# No logs available'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
          <div>
            <h3 className="text-white font-medium">{pod.name}</h3>
            <p className="text-gray-500 text-xs mt-0.5">{pod.namespace}</p>
          </div>
          <div className="flex items-center gap-2">
            <CopyButton text={logs} />
            <button
              onClick={onClose}
              className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <pre className="text-xs text-gray-400 font-mono leading-relaxed whitespace-pre-wrap">
            {logs}
          </pre>
        </div>
      </div>
    </div>
  )
}

interface PodStatusGridProps {
  pods: PodInfo[]
  loading?: boolean
  selectedNamespace?: string
  namespaces?: string[]
  onNamespaceChange?: (ns: string) => void
}

export function PodStatusGrid({
  pods,
  loading = false,
  selectedNamespace = 'all',
  namespaces = [],
  onNamespaceChange,
}: PodStatusGridProps) {
  const [selectedPod, setSelectedPod] = useState<PodInfo | null>(null)

  const filtered =
    selectedNamespace === 'all' ? pods : pods.filter((p) => p.namespace === selectedNamespace)

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-24 bg-gray-800/50 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (!filtered.length) {
    return (
      <EmptyState
        icon={Layers}
        title="No pods found"
        message="No pods matching the current namespace filter."
      />
    )
  }

  return (
    <>
      {namespaces.length > 0 && onNamespaceChange && (
        <div className="mb-4">
          <select
            value={selectedNamespace}
            onChange={(e) => onNamespaceChange(e.target.value)}
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value="all">All Namespaces</option>
            {namespaces.map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
        {filtered.map((pod) => {
          const status = getPodStatus(pod)
          const cfg = statusConfig[status]

          return (
            <button
              key={`${pod.namespace}/${pod.name}`}
              onClick={() => setSelectedPod(pod)}
              className={clsx(
                'text-left rounded-lg border p-3 hover:brightness-110 transition-all',
                cfg.card,
              )}
            >
              <div className="flex items-start gap-2 mb-2">
                <div
                  className={clsx('w-2 h-2 rounded-full mt-1.5 shrink-0', cfg.dot)}
                />
                <p className="text-gray-200 text-xs font-medium truncate leading-tight">{pod.name}</p>
              </div>
              <p className="text-gray-500 text-xs truncate">{pod.namespace}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs font-medium" style={{ color: 'inherit' }}>
                  {cfg.label}
                </span>
                {pod.restartCount > 0 && (
                  <span className="flex items-center gap-0.5 text-orange-400 text-xs">
                    <RefreshCw size={9} />
                    {pod.restartCount}
                  </span>
                )}
              </div>
              {pod.startedAt && (
                <p className="text-gray-600 text-xs mt-0.5">
                  {formatDistanceToNow(new Date(pod.startedAt), { addSuffix: true })}
                </p>
              )}
            </button>
          )
        })}
      </div>

      {selectedPod && (
        <LogsModal pod={selectedPod} onClose={() => setSelectedPod(null)} />
      )}
    </>
  )
}
