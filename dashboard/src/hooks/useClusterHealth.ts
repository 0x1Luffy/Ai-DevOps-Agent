import { useQuery } from '@tanstack/react-query'
import { fetchClusterHealth, fetchNodes } from '../api/client'

export function useClusterHealth() {
  return useQuery({
    queryKey: ['cluster-health'],
    queryFn: () => fetchClusterHealth().then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function useNodes() {
  return useQuery({
    queryKey: ['cluster-nodes'],
    queryFn: () => fetchNodes().then((r) => r.data),
    refetchInterval: 30_000,
  })
}
