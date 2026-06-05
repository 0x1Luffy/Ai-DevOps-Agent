import clsx from 'clsx'

interface ConfidenceMeterProps {
  value: number | null
  showLabel?: boolean
  compact?: boolean
}

function getColor(value: number): string {
  if (value >= 85) return 'bg-green-500'
  if (value >= 70) return 'bg-yellow-500'
  return 'bg-red-500'
}

function getTextColor(value: number): string {
  if (value >= 85) return 'text-green-400'
  if (value >= 70) return 'text-yellow-400'
  return 'text-red-400'
}

export function ConfidenceMeter({ value, showLabel = true, compact = false }: ConfidenceMeterProps) {
  if (value === null || value === undefined) {
    return <span className="text-gray-500 text-sm">N/A</span>
  }

  const pct = Math.max(0, Math.min(100, value))

  return (
    <div className={clsx('flex items-center gap-2', compact ? 'w-24' : 'w-full')}>
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all duration-300', getColor(pct))}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className={clsx('text-xs font-medium tabular-nums w-9 text-right', getTextColor(pct))}>
          {pct.toFixed(0)}%
        </span>
      )}
    </div>
  )
}
