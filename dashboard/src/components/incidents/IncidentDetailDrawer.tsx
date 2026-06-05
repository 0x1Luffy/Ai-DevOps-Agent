import { useState } from 'react'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import {
  type LucideIcon,
  X,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  Wrench,
  Bot,
  Code,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import clsx from 'clsx'
import type { Incident } from '../../types'
import { SeverityBadge } from './SeverityBadge'
import { ConfidenceMeter } from '../shared/ConfidenceMeter'
import { CopyButton } from '../shared/CopyButton'
import { IncidentTimeline } from './IncidentTimeline'

interface IncidentDetailDrawerProps {
  incident: Incident | null
  onClose: () => void
}

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
}: {
  title: string
  icon: LucideIcon
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-gray-700/60 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800/60 hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon size={14} className="text-gray-400" />
          <span className="text-gray-300 text-sm font-medium">{title}</span>
        </div>
        {open ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-500" />}
      </button>
      {open && <div className="px-4 py-4 bg-gray-900/40">{children}</div>}
    </div>
  )
}

export function IncidentDetailDrawer({ incident, onClose }: IncidentDetailDrawerProps) {
  if (!incident) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed top-0 right-0 h-full w-[600px] bg-gray-900 border-l border-gray-700 z-50 flex flex-col animate-slide-in overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-700 shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <SeverityBadge severity={incident.severity} />
              <span className="text-gray-400 text-xs font-mono bg-gray-800 px-2 py-0.5 rounded">
                {incident.namespace}
              </span>
            </div>
            <h2 className="text-white font-semibold text-base">{incident.resourceName}</h2>
            <p className="text-gray-500 text-sm mt-0.5">{incident.problemType}</p>
            <p className="text-gray-600 text-xs mt-1">
              Detected {format(new Date(incident.detectedAt), "MMM d, yyyy 'at' HH:mm:ss")}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Link
              to={`/incidents/${incident.id}`}
              className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
            >
              <ExternalLink size={12} />
              Open Full Page
            </Link>
            <button
              onClick={onClose}
              className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {/* Root Cause */}
          {incident.rootCause && (
            <CollapsibleSection title="Root Cause Analysis" icon={Bot}>
              <div className="space-y-3">
                <p className="text-gray-300 text-sm leading-relaxed">{incident.rootCause}</p>
                <div className="flex items-center gap-3">
                  <span className="text-gray-500 text-xs">Confidence:</span>
                  <div className="flex-1 max-w-xs">
                    <ConfidenceMeter value={incident.confidence} />
                  </div>
                </div>
                {incident.autoFixable && (
                  <div className="flex items-center gap-2 text-xs text-green-400">
                    <CheckCircle2 size={13} />
                    Auto-fixable
                  </div>
                )}
                {incident.preventionTip && (
                  <div className="flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
                    <Lightbulb size={13} className="text-yellow-400 shrink-0 mt-0.5" />
                    <p className="text-yellow-300 text-xs">{incident.preventionTip}</p>
                  </div>
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* Timeline */}
          {incident.timeline && incident.timeline.length > 0 && (
            <CollapsibleSection title="Timeline" icon={Wrench}>
              <IncidentTimeline events={incident.timeline} />
            </CollapsibleSection>
          )}

          {/* Fix Steps */}
          {incident.fixExecutions && incident.fixExecutions.length > 0 && (
            <CollapsibleSection title="Fix Steps Applied" icon={Wrench}>
              <div className="space-y-3">
                {incident.fixExecutions.map((exec, idx) => (
                  <div
                    key={exec.id}
                    className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-3"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-indigo-600/30 text-indigo-400 text-xs flex items-center justify-center font-mono shrink-0">
                          {idx + 1}
                        </span>
                        <span className="text-gray-300 text-sm font-medium">{exec.fixAction}</span>
                      </div>
                      <span
                        className={clsx(
                          'text-xs px-1.5 py-0.5 rounded',
                          exec.result === 'success' && 'bg-green-500/15 text-green-400',
                          exec.result === 'failed' && 'bg-red-500/15 text-red-400',
                          exec.result === 'partial' && 'bg-yellow-500/15 text-yellow-400',
                          exec.result === 'skipped' && 'bg-gray-600/20 text-gray-500',
                          exec.result === null && 'bg-gray-600/20 text-gray-500',
                        )}
                      >
                        {exec.result ?? 'pending'}
                      </span>
                    </div>
                    {exec.fixDescription && (
                      <p className="text-gray-500 text-xs mb-2">{exec.fixDescription}</p>
                    )}
                    {exec.kubectlCommands && exec.kubectlCommands.length > 0 && (
                      <div className="space-y-1.5">
                        {exec.kubectlCommands.map((cmd, cmdIdx) => (
                          <div
                            key={cmdIdx}
                            className="flex items-center justify-between bg-gray-950 rounded px-3 py-2"
                          >
                            <code className="text-green-400 text-xs font-mono flex-1 truncate">
                              {cmd}
                            </code>
                            <CopyButton text={cmd} />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Raw K8s Context */}
          {incident.fullContext && (
            <CollapsibleSection title="Raw K8s Context" icon={Code} defaultOpen={false}>
              <pre className="text-xs text-gray-400 font-mono overflow-x-auto leading-relaxed max-h-64 overflow-y-auto">
                {JSON.stringify(incident.fullContext, null, 2)}
              </pre>
            </CollapsibleSection>
          )}

          {/* AI Debug */}
          {(incident.claudePrompt || incident.claudeResponse) && (
            <CollapsibleSection title="AI Debug" icon={Bot} defaultOpen={false}>
              {incident.claudePrompt && (
                <div className="mb-3">
                  <h4 className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-2">Prompt</h4>
                  <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap overflow-x-auto leading-relaxed max-h-40 overflow-y-auto bg-gray-950 p-3 rounded border border-gray-700">
                    {incident.claudePrompt}
                  </pre>
                </div>
              )}
              {incident.claudeResponse && (
                <div>
                  <h4 className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-2">Response</h4>
                  <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap overflow-x-auto leading-relaxed max-h-48 overflow-y-auto bg-gray-950 p-3 rounded border border-gray-700">
                    {incident.claudeResponse}
                  </pre>
                </div>
              )}
            </CollapsibleSection>
          )}
        </div>
      </div>
    </>
  )
}
