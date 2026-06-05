import clsx from 'clsx'

interface ClusterHealthScoreProps {
  score: number
  status: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY'
  loading?: boolean
}

function getScoreColor(score: number) {
  if (score >= 80) return { stroke: '#22c55e', text: 'text-green-400', label: 'text-green-500' }
  if (score >= 60) return { stroke: '#eab308', text: 'text-yellow-400', label: 'text-yellow-500' }
  return { stroke: '#ef4444', text: 'text-red-400', label: 'text-red-500' }
}

const RADIUS = 52
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function ClusterHealthScore({ score, status, loading = false }: ClusterHealthScoreProps) {
  const colors = getScoreColor(score)
  const offset = CIRCUMFERENCE - (score / 100) * CIRCUMFERENCE

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-44">
        <div className="w-28 h-28 rounded-full border-4 border-gray-700 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          {/* Track */}
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            stroke="#1f2937"
            strokeWidth="10"
          />
          {/* Progress */}
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            stroke={colors.stroke}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={clsx('text-3xl font-bold tabular-nums', colors.text)}>
            {Math.round(score)}
          </span>
          <span className="text-gray-500 text-xs mt-0.5">/ 100</span>
        </div>
      </div>
      <span
        className={clsx(
          'text-sm font-semibold px-3 py-1 rounded-full',
          status === 'HEALTHY' && 'bg-green-500/10 text-green-400',
          status === 'DEGRADED' && 'bg-yellow-500/10 text-yellow-400',
          status === 'UNHEALTHY' && 'bg-red-500/10 text-red-400',
        )}
      >
        {status}
      </span>
    </div>
  )
}
