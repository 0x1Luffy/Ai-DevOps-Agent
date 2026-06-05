import { useQuery } from '@tanstack/react-query'
import { fetchDashboardSummary } from '../api/client'
import { useStore } from '../store'
import { useEffect } from 'react'

export function useDashboard() {
  const setSummary = useStore((s) => s.setSummary)

  const query = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => fetchDashboardSummary().then((r) => r.data),
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (query.data) {
      setSummary(query.data)
    }
  }, [query.data, setSummary])

  return query
}
