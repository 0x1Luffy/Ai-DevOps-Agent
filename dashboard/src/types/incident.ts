export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type IncidentStatus = 'open' | 'diagnosing' | 'needs_approval' | 'fixing' | 'fixed' | 'still_broken' | 'escalated' | 'manual' | 'skipped'

export interface Incident {
  id: string
  detectedAt: string
  resourceType: string
  resourceName: string
  namespace: string
  problemType: string
  severity: Severity
  rootCause: string | null
  confidence: number | null
  autoFixable: boolean
  fixPlan: FixStep[] | null
  preventionTip: string | null
  estimatedRecovery: string | null
  relatedResources: string[] | null
  status: IncidentStatus
  resolvedAt: string | null
  slackMessageTs: string | null
  claudePrompt: string | null
  claudeResponse: string | null
  fullContext: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
  fixExecutions?: FixExecution[]
  timeline?: TimelineEvent[]
}

export interface FixStep {
  action: string
  params: Record<string, unknown>
  description: string
  kubectlEquivalent: string
}

export interface FixExecution {
  id: string
  incidentId: string
  executedAt: string
  fixAction: string
  fixParams: Record<string, unknown> | null
  fixDescription: string | null
  kubectlCommands: string[] | null
  executedBy: string
  approverSlackId: string | null
  result: 'success' | 'failed' | 'partial' | 'skipped' | null
  verificationStatus: 'fixed' | 'still_broken' | 'degraded' | 'pending' | 'skipped' | null
  verifiedAt: string | null
  errorMessage: string | null
  executionDurationMs: number | null
}

export interface TimelineEvent {
  timestamp: string
  type: 'detected' | 'diagnosed' | 'approval_sent' | 'approved' | 'fix_applied' | 'verifying' | 'verified' | 'escalated' | 'failed'
  title: string
  description: string
  details?: Record<string, unknown>
}

export interface IncidentStats {
  total: number
  open: number
  fixing: number
  fixed: number
  bySeverity: Record<Severity, number>
  byProblemType: Record<string, number>
  avgResolutionTimeMinutes: number
}
