import { useState } from 'react'
import { X, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import type { Incident } from '../../types'
import { SeverityBadge } from '../incidents/SeverityBadge'
import { FixStepsViewer } from './FixStepsViewer'

interface FixApprovalModalProps {
  incident: Incident
  onApprove: (approver: string) => Promise<void>
  onCancel: () => void
}

export function FixApprovalModal({ incident, onApprove, onCancel }: FixApprovalModalProps) {
  const [approver, setApprover] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleApprove = async () => {
    if (!approver.trim()) {
      setError('Please enter your name or Slack ID.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await onApprove(approver.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve fix.')
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />

      {/* Modal */}
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-5 border-b border-gray-700 shrink-0">
          <div>
            <h2 className="text-white font-semibold text-lg">Approve Fix</h2>
            <div className="flex items-center gap-2 mt-1.5">
              <SeverityBadge severity={incident.severity} size="sm" />
              <span className="text-gray-400 text-sm">{incident.resourceName}</span>
              <span className="text-gray-600 text-xs">·</span>
              <span className="text-gray-500 text-sm">{incident.namespace}</span>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <div>
            <h3 className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">
              Problem
            </h3>
            <p className="text-gray-300 text-sm">{incident.problemType}</p>
            {incident.rootCause && (
              <p className="text-gray-500 text-xs mt-1">{incident.rootCause}</p>
            )}
          </div>

          {incident.fixPlan && incident.fixPlan.length > 0 && (
            <div>
              <h3 className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-3">
                Proposed Fix Steps
              </h3>
              <FixStepsViewer steps={incident.fixPlan} />
            </div>
          )}

          {/* Approver input */}
          <div>
            <label className="block text-gray-400 text-xs font-medium uppercase tracking-wider mb-2">
              Your name or Slack ID
            </label>
            <input
              type="text"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder="e.g. john.doe or @johndoe"
              className="w-full bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-4 py-2.5 placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
            {error && <p className="text-red-400 text-xs mt-1.5">{error}</p>}
          </div>

          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
            <p className="text-yellow-300 text-xs">
              By approving, you authorize the AutoPilot agent to execute the above fix steps
              against the production cluster. This action cannot be undone.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-700 shrink-0">
          <button
            onClick={onCancel}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            <XCircle size={14} />
            Cancel
          </button>
          <button
            onClick={handleApprove}
            disabled={loading || !approver.trim()}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Approving...
              </>
            ) : (
              <>
                <CheckCircle size={14} />
                Approve Fix
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
