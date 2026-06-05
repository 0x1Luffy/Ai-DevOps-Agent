import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings,
  Shield,
  AlertTriangle,
  Save,
  Loader2,
  CheckCircle,
  X,
  Plus,
} from 'lucide-react'
import clsx from 'clsx'
import { fetchAgentConfig, updateAgentConfig } from '../api/client'
import type { AgentConfig } from '../types'
import { useStore } from '../store'

const HARD_RULES = [
  'Never delete PersistentVolumeClaims (PVCs)',
  'Never scale production StatefulSets below current replicas without approval',
  'Never modify RBAC ClusterRole/ClusterRoleBinding resources',
  'Never delete Namespaces',
  'Always require human approval for changes to kube-system namespace',
  'Never auto-fix incidents with confidence below the configured threshold',
  'Never execute more than 3 sequential fix attempts without verification',
  'Always preserve existing ResourceQuota settings',
  'Never modify NetworkPolicy rules without explicit approval',
  'Dry-run mode: log all actions but do not apply any changes to the cluster',
]

interface ToggleSwitchProps {
  enabled: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
}

function ToggleSwitch({ enabled, onChange, disabled = false }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!enabled)}
      disabled={disabled}
      className={clsx(
        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none',
        enabled ? 'bg-indigo-600' : 'bg-gray-700',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <span
        className={clsx(
          'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
          enabled ? 'translate-x-6' : 'translate-x-1',
        )}
      />
    </button>
  )
}

interface NamespaceTagInputProps {
  namespaces: string[]
  onChange: (ns: string[]) => void
}

function NamespaceTagInput({ namespaces, onChange }: NamespaceTagInputProps) {
  const [input, setInput] = useState('')

  const add = () => {
    const val = input.trim()
    if (val && !namespaces.includes(val)) {
      onChange([...namespaces, val])
      setInput('')
    }
  }

  const remove = (ns: string) => {
    onChange(namespaces.filter((n) => n !== ns))
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 min-h-8">
        {namespaces.map((ns) => (
          <span
            key={ns}
            className="inline-flex items-center gap-1.5 bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 text-xs font-medium px-2.5 py-1 rounded-full"
          >
            {ns}
            <button
              type="button"
              onClick={() => remove(ns)}
              className="hover:text-indigo-200 transition-colors"
            >
              <X size={11} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder="Add namespace..."
          className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 w-48 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
        />
        <button
          type="button"
          onClick={add}
          className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const queryClient = useQueryClient()
  const setAgentConfig = useStore((s) => s.setAgentConfig)
  const [saved, setSaved] = useState(false)
  const [localConfig, setLocalConfig] = useState<AgentConfig | null>(null)

  const { data: config, isLoading } = useQuery({
    queryKey: ['agent-config'],
    queryFn: () => fetchAgentConfig().then((r) => r.data),
  })

  useEffect(() => {
    if (config && !localConfig) {
      setLocalConfig(config)
    }
  }, [config, localConfig])

  const mutation = useMutation({
    mutationFn: (cfg: Partial<AgentConfig>) => updateAgentConfig(cfg).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.setQueryData(['agent-config'], data)
      setAgentConfig(data as AgentConfig)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const update = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) => {
    setLocalConfig((prev) => prev ? { ...prev, [key]: value } : prev)
  }

  const handleSave = () => {
    if (localConfig) {
      mutation.mutate(localConfig)
    }
  }

  if (isLoading || !localConfig) {
    return (
      <div className="space-y-4 max-w-2xl">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 bg-gray-800/50 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Dry Run Warning */}
      {localConfig.dryRun && (
        <div className="flex items-start gap-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
          <AlertTriangle size={18} className="text-yellow-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-yellow-300 font-medium text-sm">Dry Run Mode Active</p>
            <p className="text-yellow-400/70 text-xs mt-1">
              The agent will log all actions but will NOT apply any changes to the cluster. Disable dry run to enable automatic fixes.
            </p>
          </div>
        </div>
      )}

      {/* Agent Behavior Toggles */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-2 mb-1">
          <Settings size={16} className="text-indigo-400" />
          <h2 className="text-gray-200 font-semibold">Agent Behavior</h2>
        </div>

        {/* Enable Auto-Fix */}
        <div className="flex items-center justify-between py-3 border-b border-gray-800">
          <div>
            <p className="text-gray-300 text-sm font-medium">Enable Auto-Fix</p>
            <p className="text-gray-600 text-xs mt-0.5">
              Allow the agent to automatically apply approved fixes to the cluster.
            </p>
          </div>
          <ToggleSwitch
            enabled={localConfig.enableAutoFix}
            onChange={(v) => update('enableAutoFix', v)}
          />
        </div>

        {/* Dry Run */}
        <div className="flex items-center justify-between py-3 border-b border-gray-800">
          <div>
            <p className="text-gray-300 text-sm font-medium">Dry Run Mode</p>
            <p className="text-gray-600 text-xs mt-0.5">
              Simulate fixes without making real changes. Useful for testing.
            </p>
          </div>
          <ToggleSwitch
            enabled={localConfig.dryRun}
            onChange={(v) => update('dryRun', v)}
          />
        </div>

        {/* Drift Auto-Correct */}
        <div className="flex items-center justify-between py-3">
          <div>
            <p className="text-gray-300 text-sm font-medium">Drift Auto-Correct</p>
            <p className="text-gray-600 text-xs mt-0.5">
              Automatically correct configuration drift from the desired state.
            </p>
          </div>
          <ToggleSwitch
            enabled={localConfig.driftAutoCorrect}
            onChange={(v) => update('driftAutoCorrect', v)}
          />
        </div>
      </div>

      {/* Thresholds */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
        <h2 className="text-gray-200 font-semibold">Thresholds & Intervals</h2>

        {/* Confidence Threshold Slider */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-gray-300 text-sm font-medium">
              AI Confidence Threshold
            </label>
            <span className="text-indigo-400 font-semibold tabular-nums text-sm">
              {localConfig.confidenceThreshold}%
            </span>
          </div>
          <input
            type="range"
            min={50}
            max={100}
            step={5}
            value={localConfig.confidenceThreshold}
            onChange={(e) => update('confidenceThreshold', Number(e.target.value))}
            className="w-full accent-indigo-500"
          />
          <div className="flex justify-between text-gray-600 text-xs">
            <span>50% (permissive)</span>
            <span>100% (strict)</span>
          </div>
        </div>

        {/* Scan Interval */}
        <div className="flex items-center justify-between py-3 border-t border-gray-800">
          <div>
            <label className="text-gray-300 text-sm font-medium">Scan Interval</label>
            <p className="text-gray-600 text-xs mt-0.5">How often to scan for incidents.</p>
          </div>
          <select
            value={localConfig.scanIntervalSeconds}
            onChange={(e) => update('scanIntervalSeconds', Number(e.target.value))}
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={120}>2 minutes</option>
            <option value={300}>5 minutes</option>
            <option value={600}>10 minutes</option>
          </select>
        </div>

        {/* Post-Fix Verify Delay */}
        <div className="flex items-center justify-between py-3 border-t border-gray-800">
          <div>
            <label className="text-gray-300 text-sm font-medium">Post-Fix Verify Delay</label>
            <p className="text-gray-600 text-xs mt-0.5">Wait time before verifying a fix.</p>
          </div>
          <select
            value={localConfig.postFixVerifyDelaySeconds}
            onChange={(e) => update('postFixVerifyDelaySeconds', Number(e.target.value))}
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={120}>2 minutes</option>
            <option value={300}>5 minutes</option>
          </select>
        </div>

        {/* Slack Approval Timeout */}
        <div className="flex items-center justify-between py-3 border-t border-gray-800">
          <div>
            <label className="text-gray-300 text-sm font-medium">Slack Approval Timeout</label>
            <p className="text-gray-600 text-xs mt-0.5">Auto-escalate after this duration.</p>
          </div>
          <select
            value={localConfig.slackApprovalTimeoutMinutes}
            onChange={(e) => update('slackApprovalTimeoutMinutes', Number(e.target.value))}
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value={5}>5 minutes</option>
            <option value={10}>10 minutes</option>
            <option value={15}>15 minutes</option>
            <option value={30}>30 minutes</option>
            <option value={60}>1 hour</option>
          </select>
        </div>
      </div>

      {/* Target Namespaces */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-gray-200 font-semibold mb-4">Target Namespaces</h2>
        <p className="text-gray-600 text-xs mb-4">
          The agent will only monitor and fix issues in these namespaces. Leave empty to monitor all namespaces.
        </p>
        <NamespaceTagInput
          namespaces={localConfig.targetNamespaces}
          onChange={(ns) => update('targetNamespaces', ns)}
        />
      </div>

      {/* Hard Rules */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-green-400" />
          <h2 className="text-gray-200 font-semibold">Safety Hard Rules</h2>
          <span className="text-gray-600 text-xs ml-1">(read-only)</span>
        </div>
        <p className="text-gray-600 text-xs mb-4">
          These rules are hardcoded and cannot be overridden by configuration.
        </p>
        <div className="space-y-2">
          {HARD_RULES.map((rule, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2.5 bg-gray-800/60 rounded-lg px-4 py-2.5"
            >
              <Shield size={12} className="text-green-500 shrink-0 mt-0.5" />
              <span className="text-gray-400 text-sm leading-snug">{rule}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Save button */}
      <div className="flex items-center justify-end gap-3 py-2">
        {mutation.isError && (
          <p className="text-red-400 text-sm">Failed to save. Please try again.</p>
        )}
        {saved && (
          <div className="flex items-center gap-1.5 text-green-400 text-sm">
            <CheckCircle size={14} />
            Saved successfully
          </div>
        )}
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {mutation.isPending ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save size={14} />
              Save Settings
            </>
          )}
        </button>
      </div>
    </div>
  )
}
