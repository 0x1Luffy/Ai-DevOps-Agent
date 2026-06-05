import clsx from 'clsx'

interface ResourceUsageBarProps {
  label: string
  used: number
  total: number
  unit?: string
  formatValue?: (v: number) => string
}

function pct(used: number, total: number) {
  if (total === 0) return 0
  return Math.min(100, (used / total) * 100)
}

function getBarColor(p: number): string {
  if (p >= 90) return 'bg-red-500'
  if (p >= 75) return 'bg-yellow-500'
  return 'bg-green-500'
}

function defaultFormat(v: number): string {
  return v.toFixed(0)
}

export function ResourceUsageBar({
  label,
  used,
  total,
  unit = '',
  formatValue = defaultFormat,
}: ResourceUsageBarProps) {
  const p = pct(used, total)

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400 font-medium">{label}</span>
        <span className="text-gray-500 tabular-nums">
          {formatValue(used)}
          {unit} / {formatValue(total)}
          {unit}
        </span>
      </div>
      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all duration-500', getBarColor(p))}
          style={{ width: `${p}%` }}
        />
      </div>
      <div className="flex justify-end">
        <span
          className={clsx(
            'text-xs tabular-nums',
            p >= 90 ? 'text-red-400' : p >= 75 ? 'text-yellow-400' : 'text-green-400',
          )}
        >
          {p.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}
