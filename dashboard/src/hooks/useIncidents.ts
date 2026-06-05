import { useQuery } from '@tanstack/react-query'
import { fetchIncidents, fetchIncident, fetchIncidentStats } from '../api/client'

export interface IncidentFilters {
  page?: number
  limit?: number
  namespace?: string
  severity?: string
  status?: string
  problemType?: string
  search?: string
  from?: string
  to?: string
}

export function useIncidents(filters: IncidentFilters = {}) {
  return useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => fetchIncidents(filters as Record<string, unknown>).then((r) => r.data),
    staleTime: 15_000,
  })
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ['incident', id],
    queryFn: () => fetchIncident(id).then((r) => r.data),
    enabled: Boolean(id),
    staleTime: 10_000,
  })
}

export function useIncidentStats() {
  return useQuery({
    queryKey: ['incident-stats'],
    queryFn: () => fetchIncidentStats().then((r) => r.data),
    refetchInterval: 30_000,
  })
}
