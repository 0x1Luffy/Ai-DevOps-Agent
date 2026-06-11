import axios from 'axios'
import type {
  Incident,
  IncidentStats,
  FixExecution,
  FixPattern,
  DashboardSummary,
  ClusterHealth,
  NodeInfo,
  JenkinsIncident,
  PipelineHealth,
  AgentConfig,
} from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: { Authorization: `Bearer ${import.meta.env.VITE_API_KEY || 'change-me-in-production'}` },
})

export const fetchIncidents = (params: Record<string, unknown>) =>
  api.get<{ incidents: Incident[]; total: number; page: number; totalPages: number }>('/api/incidents', { params })

export const fetchIncident = (id: string) =>
  api.get<Incident>(`/api/incidents/${id}`)

export const fetchIncidentStats = () =>
  api.get<IncidentStats>('/api/incidents/stats')

export const fetchFixes = (params: Record<string, unknown>) =>
  api.get<{ fixes: FixExecution[]; total: number; successRate: number }>('/api/fixes', { params })

export const fetchFixPatterns = () =>
  api.get<FixPattern[]>('/api/fixes/patterns')

export const approveFix = (incidentId: string, approver: string) =>
  api.post(`/api/fixes/${incidentId}/approve`, { approver })

export const fetchDashboardSummary = () =>
  api.get<DashboardSummary>('/api/dashboard/summary')

export const fetchClusterHealth = () =>
  api.get<ClusterHealth>('/api/cluster/health')

export const fetchNodes = () =>
  api.get<NodeInfo[]>('/api/cluster/nodes')

export const fetchNamespaces = () =>
  api.get<unknown[]>('/api/cluster/namespaces')

export const fetchJenkinsIncidents = (params: Record<string, unknown>) =>
  api.get<{ incidents: JenkinsIncident[]; total: number; failuresByType: Record<string, number> }>('/api/jenkins/incidents', { params })

export const fetchPipelineHealth = () =>
  api.get<{ jobs: PipelineHealth[] }>('/api/jenkins/pipeline-health')

export const fetchMetricsTrends = (days: number) =>
  api.get('/api/metrics/trends', { params: { days } })

export const fetchAgentConfig = () =>
  api.get<AgentConfig>('/api/settings/config')

export const updateAgentConfig = (config: Partial<AgentConfig>) =>
  api.patch('/api/settings/config', config)

export default api
