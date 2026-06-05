import { useParams, Link } from 'react-router-dom'
import { format } from 'date-fns'
import {
  ArrowLeft,
  Lightbulb,
  Bot,
  Wrench,
  Code,
  CheckCircle2,
  ExternalLink,
} from 'lucide-react'
import { useIncident } from '../hooks/useIncidents'
import { SeverityBadge } from '../components/incidents/SeverityBadge'
import { ConfidenceMeter } from '../components/shared/ConfidenceMeter'
import { IncidentTimeline } from '../components/incidents/IncidentTimeline'
import { FixStepsViewer } from '../components/fixes/FixStepsViewer'
import { CopyButton } from '../components/shared/CopyButton'

export function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: incident, isLoading, error } = useIncident(id ?? '')

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-4xl">
        <div className="h-8 w-32 bg-gray-800 rounded animate-pulse" />
        <div className="h-32 bg-gray-800/50 rounded-xl animate-pulse" />
        <div className="h-48 bg-gray-800/50 rounded-xl animate-pulse" />
        <div className="h-64 bg-gray-800/50 rounded-xl animate-pulse" />
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-gray-400 mb-3">Incident not found or failed to load.</p>
        <Link to="/incidents" className="text-indigo-400 hover:text-indigo-300 text-sm flex items-center gap-1">
          <ArrowLeft size={14} />
          Back to Incidents
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back */}
      <Link
        to="/incidents"
        className="inline-flex items-center gap-1.5 text-gray-500 hover:text-gray-300 text-sm transition-colors"
      >
        <ArrowLeft size={14} />
        Back to Incidents
      </Link>

      {/* Header card */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <SeverityBadge severity={incident.severity} />
              <span className="text-gray-400 text-xs font-mono bg-gray-800 px-2 py-0.5 rounded">
                {incident.namespace}
              </span>
              <span className="text-gray-600 text-xs">{incident.resourceType}</span>
            </div>
            <h1 className="text-white text-2xl font-bold">{incident.resourceName}</h1>
            <p className="text-gray-400 mt-1">{incident.problemType}</p>
            <p className="text-gray-600 text-sm mt-2">
              Detected {format(new Date(incident.detectedAt), "MMMM d, yyyy 'at' HH:mm:ss")}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <span
              className="text-sm font-medium px-3 py-1.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/30"
            >
              {incident.status.replace('_', ' ')}
            </span>
            {incident.resolvedAt && (
              <p className="text-gray-600 text-xs mt-2">
                Resolved {format(new Date(incident.resolvedAt), 'MMM d, HH:mm')}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Root Cause */}
      {incident.rootCause && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Bot size={16} className="text-purple-400" />
            <h2 className="text-gray-200 font-semibold">Root Cause Analysis</h2>
          </div>
          <p className="text-gray-300 leading-relaxed">{incident.rootCause}</p>
          <div className="flex items-center gap-3">
            <span className="text-gray-500 text-sm">Confidence:</span>
            <div className="flex-1 max-w-sm">
              <ConfidenceMeter value={incident.confidence} />
            </div>
          </div>
          {incident.autoFixable && (
            <div className="flex items-center gap-2 text-sm text-green-400">
              <CheckCircle2 size={15} />
              This issue is auto-fixable
            </div>
          )}
          {incident.preventionTip && (
            <div className="flex items-start gap-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
              <Lightbulb size={15} className="text-yellow-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-yellow-400 text-xs font-medium uppercase tracking-wider mb-1">Prevention Tip</p>
                <p className="text-yellow-300 text-sm">{incident.preventionTip}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      {incident.timeline && incident.timeline.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <Wrench size={16} className="text-indigo-400" />
            <h2 className="text-gray-200 font-semibold">Incident Timeline</h2>
          </div>
          <IncidentTimeline events={incident.timeline} />
        </div>
      )}

      {/* Fix Plan */}
      {incident.fixPlan && incident.fixPlan.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <Wrench size={16} className="text-yellow-400" />
            <h2 className="text-gray-200 font-semibold">Fix Steps</h2>
          </div>
          <FixStepsViewer steps={incident.fixPlan} executions={incident.fixExecutions} />
        </div>
      )}

      {/* Raw K8s Context */}
      {incident.fullContext && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center justify-between gap-2 mb-4">
            <div className="flex items-center gap-2">
              <Code size={16} className="text-gray-400" />
              <h2 className="text-gray-200 font-semibold">Raw K8s Context</h2>
            </div>
            <CopyButton text={JSON.stringify(incident.fullContext, null, 2)} />
          </div>
          <pre className="text-xs text-gray-400 font-mono overflow-x-auto leading-relaxed max-h-80 overflow-y-auto bg-gray-950 p-4 rounded-lg border border-gray-700">
            {JSON.stringify(incident.fullContext, null, 2)}
          </pre>
        </div>
      )}

      {/* AI Debug */}
      {(incident.claudePrompt || incident.claudeResponse) && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2">
            <Bot size={16} className="text-purple-400" />
            <h2 className="text-gray-200 font-semibold">AI Debug Information</h2>
          </div>
          {incident.claudePrompt && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-gray-500 text-xs font-medium uppercase tracking-wider">Prompt</h3>
                <CopyButton text={incident.claudePrompt} />
              </div>
              <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap overflow-x-auto leading-relaxed max-h-48 overflow-y-auto bg-gray-950 p-4 rounded-lg border border-gray-700">
                {incident.claudePrompt}
              </pre>
            </div>
          )}
          {incident.claudeResponse && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-gray-500 text-xs font-medium uppercase tracking-wider">Response</h3>
                <CopyButton text={incident.claudeResponse} />
              </div>
              <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap overflow-x-auto leading-relaxed max-h-64 overflow-y-auto bg-gray-950 p-4 rounded-lg border border-gray-700">
                {incident.claudeResponse}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
