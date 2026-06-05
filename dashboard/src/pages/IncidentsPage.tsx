import { useState } from 'react'
import { Search, ChevronLeft, ChevronRight, SlidersHorizontal } from 'lucide-react'
import { useIncidents, type IncidentFilters } from '../hooks/useIncidents'
import type { Incident, Severity, IncidentStatus } from '../types'
import { IncidentTable } from '../components/incidents/IncidentTable'
import { IncidentDetailDrawer } from '../components/incidents/IncidentDetailDrawer'

const SEVERITIES: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
const STATUSES: IncidentStatus[] = [
  'open', 'diagnosing', 'needs_approval', 'fixing', 'fixed', 'still_broken', 'escalated', 'manual', 'skipped',
]

export function IncidentsPage() {
  const [filters, setFilters] = useState<IncidentFilters>({ page: 1, limit: 20 })
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [searchInput, setSearchInput] = useState('')

  const { data, isLoading, error } = useIncidents(filters)

  const updateFilter = <K extends keyof IncidentFilters>(key: K, value: IncidentFilters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }))
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    updateFilter('search', searchInput || undefined)
  }

  const totalPages = data?.totalPages ?? 1
  const currentPage = data?.page ?? 1

  return (
    <div className="space-y-5 max-w-screen-xl">
      {/* Filters */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <SlidersHorizontal size={14} className="text-gray-500" />
          <span className="text-gray-400 text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search resource, problem..."
                className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg pl-9 pr-4 py-2 w-56 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </form>

          {/* Severity */}
          <select
            value={filters.severity ?? ''}
            onChange={(e) => updateFilter('severity', e.target.value || undefined)}
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Severities</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {/* Status */}
          <select
            value={filters.status ?? ''}
            onChange={(e) => updateFilter('status', e.target.value || undefined)}
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace('_', ' ')}</option>
            ))}
          </select>

          {/* Namespace */}
          <input
            type="text"
            value={filters.namespace ?? ''}
            onChange={(e) => updateFilter('namespace', e.target.value || undefined)}
            placeholder="Namespace"
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 w-36 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />

          {/* Problem type */}
          <input
            type="text"
            value={filters.problemType ?? ''}
            onChange={(e) => updateFilter('problemType', e.target.value || undefined)}
            placeholder="Problem type"
            className="bg-gray-800 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-2 w-40 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />

          {/* Date range */}
          <input
            type="date"
            value={filters.from ?? ''}
            onChange={(e) => updateFilter('from', e.target.value || undefined)}
            className="bg-gray-800 border border-gray-600 text-gray-400 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          />
          <span className="text-gray-600 self-center text-sm">to</span>
          <input
            type="date"
            value={filters.to ?? ''}
            onChange={(e) => updateFilter('to', e.target.value || undefined)}
            className="bg-gray-800 border border-gray-600 text-gray-400 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {error ? (
          <div className="p-8 text-center text-gray-400">
            Failed to load incidents. Please try again.
          </div>
        ) : (
          <IncidentTable
            incidents={data?.incidents ?? []}
            loading={isLoading}
            onSelect={setSelectedIncident}
          />
        )}

        {/* Pagination */}
        {!isLoading && data && data.total > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <p className="text-gray-500 text-sm">
              Showing {(currentPage - 1) * (filters.limit ?? 20) + 1}–
              {Math.min(currentPage * (filters.limit ?? 20), data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setFilters((p) => ({ ...p, page: (p.page ?? 1) - 1 }))}
                disabled={currentPage <= 1}
                className="p-1.5 rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-gray-400 text-sm tabular-nums">
                {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => setFilters((p) => ({ ...p, page: (p.page ?? 1) + 1 }))}
                disabled={currentPage >= totalPages}
                className="p-1.5 rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Drawer */}
      <IncidentDetailDrawer
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  )
}
