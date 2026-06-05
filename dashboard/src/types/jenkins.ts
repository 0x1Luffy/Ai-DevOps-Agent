export type JenkinsFailureType =
  | 'FLAKY_NETWORK' | 'NPM_PEER_DEP_CONFLICT' | 'NPM_REGISTRY_TIMEOUT' | 'NPM_AUDIT_FAIL'
  | 'NPM_CI_LOCK_MISMATCH' | 'DOCKER_BUILD_FAIL' | 'DOCKER_PUSH_FAIL' | 'DOCKER_IN_DOCKER_FAIL'
  | 'TEST_FAILURE' | 'FLAKY_TEST' | 'KUBECTL_APPLY_FAIL' | 'BUILD_OOM' | 'MISSING_SECRET'
  | 'PERMISSION_DENIED' | 'TIMEOUT' | 'LIVENESS_PROBE_FAIL' | 'SHARED_LIBRARY_FAIL'
  | 'SCM_CHECKOUT_FAIL' | 'WORKSPACE_DIRTY' | 'AGENT_OFFLINE' | 'NODE_VERSION_MISMATCH'
  | 'POST_BUILD_ACTION_FAIL' | 'QUALITY_GATE_FAIL' | 'CREDENTIALS_MISSING' | 'ARM64_COMPAT_FAIL'
  | 'UNKNOWN'

export interface JenkinsIncident {
  id: string
  detectedAt: string
  jobName: string
  buildNumber: number | null
  branch: string | null
  commitSha: string | null
  failureType: JenkinsFailureType | null
  failingStage: string | null
  failingLine: string | null
  aiDiagnosis: Record<string, unknown> | null
  actionTaken: string | null
  retryCount: number
  resolved: boolean
  resolvedAt: string | null
  githubIssueUrl: string | null
  buildDurationSeconds: number | null
  consoleLogSnippet: string | null
}

export interface PipelineHealth {
  name: string
  successRate: number
  lastBuild: string | null
  totalBuilds: number
  commonFailureType: string | null
  avgDurationSeconds: number | null
}
