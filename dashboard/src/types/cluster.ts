export interface NodeInfo {
  name: string
  role: 'control-plane' | 'worker'
  status: 'Ready' | 'NotReady'
  cpuAllocatable: string
  cpuUsed: string
  memoryAllocatable: string
  memoryUsed: string
  podCount: number
  podCapacity: number
  conditions: NodeCondition[]
  taints: NodeTaint[]
}

export interface NodeCondition {
  type: string
  status: string
  reason: string | null
}

export interface NodeTaint {
  key: string
  value: string | null
  effect: string
}

export interface ClusterHealth {
  status: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY'
  score: number
  issues: HealthIssue[]
  recommendation: string
  checks: {
    nodesReady: { score: number; details: string }
    podHealth: { score: number; details: string }
    pvcHealth: { score: number; details: string }
    recentIncidents: { score: number; details: string }
  }
}

export interface HealthIssue {
  type: string
  detail: string
  severity: string
}

export interface DashboardSummary {
  clusterHealthScore: number
  clusterStatus: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY'
  openIncidents: number
  criticalIncidents: number
  fixedLast24h: number
  fixSuccessRate: number
  activeApprovals: number
  jenkinsFailures24h: number
  topProblems: Array<{ type: string; count: number }>
  recentActivity: ActivityEvent[]
  incidentTrend: Array<{ date: string; count: number }>
}

export interface ActivityEvent {
  id: string
  timestamp: string
  type: 'detected' | 'fixed' | 'fixing' | 'escalated' | 'retried' | 'jenkins_failure' | 'approval_needed'
  description: string
  resourceName?: string
  namespace?: string
  severity?: string
}

export type LLMProvider = 'anthropic' | 'openai'

export interface AgentConfig {
  enableAutoFix: boolean
  dryRun: boolean
  driftAutoCorrect: boolean
  confidenceThreshold: number
  scanIntervalSeconds: number
  postFixVerifyDelaySeconds: number
  slackApprovalTimeoutMinutes: number
  targetNamespaces: string[]
  llmProvider: LLMProvider
  claudeModel: string
  openaiModel: string
}
