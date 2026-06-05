export interface FixPattern {
  id: string
  problemPattern: string
  fixAction: string
  successCount: number
  failureCount: number
  successRate: number
  lastUsed: string | null
}

export interface FixesResponse {
  fixes: import('./incident').FixExecution[]
  total: number
  successRate: number
}
