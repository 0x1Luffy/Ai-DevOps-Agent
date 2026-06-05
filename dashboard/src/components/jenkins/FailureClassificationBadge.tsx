import clsx from 'clsx'
import type { JenkinsFailureType } from '../../types'

const categoryMap: Record<string, { label: string; className: string }> = {
  NPM_PEER_DEP_CONFLICT: { label: 'NPM', className: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
  NPM_REGISTRY_TIMEOUT: { label: 'NPM', className: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
  NPM_AUDIT_FAIL: { label: 'NPM', className: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
  NPM_CI_LOCK_MISMATCH: { label: 'NPM', className: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
  DOCKER_BUILD_FAIL: { label: 'Docker', className: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  DOCKER_PUSH_FAIL: { label: 'Docker', className: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  DOCKER_IN_DOCKER_FAIL: { label: 'Docker', className: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  KUBECTL_APPLY_FAIL: { label: 'K8s', className: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30' },
  LIVENESS_PROBE_FAIL: { label: 'K8s', className: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30' },
  TEST_FAILURE: { label: 'Test', className: 'bg-red-500/15 text-red-400 border-red-500/30' },
  FLAKY_TEST: { label: 'Test', className: 'bg-red-500/15 text-red-400 border-red-500/30' },
  FLAKY_NETWORK: { label: 'Network', className: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
  BUILD_OOM: { label: 'OOM', className: 'bg-pink-500/15 text-pink-400 border-pink-500/30' },
  MISSING_SECRET: { label: 'Secret', className: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' },
  PERMISSION_DENIED: { label: 'Auth', className: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' },
  CREDENTIALS_MISSING: { label: 'Auth', className: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' },
  TIMEOUT: { label: 'Timeout', className: 'bg-gray-500/15 text-gray-400 border-gray-500/30' },
  AGENT_OFFLINE: { label: 'Agent', className: 'bg-gray-500/15 text-gray-400 border-gray-500/30' },
  WORKSPACE_DIRTY: { label: 'Workspace', className: 'bg-gray-500/15 text-gray-400 border-gray-500/30' },
  NODE_VERSION_MISMATCH: { label: 'Node', className: 'bg-lime-500/15 text-lime-400 border-lime-500/30' },
  SCM_CHECKOUT_FAIL: { label: 'SCM', className: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30' },
  SHARED_LIBRARY_FAIL: { label: 'Library', className: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30' },
  POST_BUILD_ACTION_FAIL: { label: 'Post Build', className: 'bg-gray-500/15 text-gray-400 border-gray-500/30' },
  QUALITY_GATE_FAIL: { label: 'Quality', className: 'bg-rose-500/15 text-rose-400 border-rose-500/30' },
  ARM64_COMPAT_FAIL: { label: 'ARM64', className: 'bg-violet-500/15 text-violet-400 border-violet-500/30' },
  UNKNOWN: { label: 'Unknown', className: 'bg-gray-700/30 text-gray-500 border-gray-600/30' },
}

interface FailureClassificationBadgeProps {
  failureType: JenkinsFailureType
}

export function FailureClassificationBadge({ failureType }: FailureClassificationBadgeProps) {
  const cfg = categoryMap[failureType] ?? categoryMap.UNKNOWN

  return (
    <span
      className={clsx(
        'inline-flex items-center text-xs font-medium px-1.5 py-0.5 rounded border',
        cfg.className,
      )}
    >
      {cfg.label}
    </span>
  )
}
