import clsx from 'clsx'

type Status = 'healthy' | 'warning' | 'error' | 'info' | 'unknown'

interface StatusDotProps {
  status: Status
  pulse?: boolean
  size?: 'sm' | 'md' | 'lg'
}

const colorMap: Record<Status, string> = {
  healthy: 'bg-green-500',
  warning: 'bg-yellow-500',
  error: 'bg-red-500',
  info: 'bg-blue-500',
  unknown: 'bg-gray-500',
}

const sizeMap = {
  sm: 'w-2 h-2',
  md: 'w-2.5 h-2.5',
  lg: 'w-3 h-3',
}

export function StatusDot({ status, pulse = false, size = 'md' }: StatusDotProps) {
  return (
    <span className="relative inline-flex">
      <span
        className={clsx(
          'rounded-full',
          colorMap[status],
          sizeMap[size],
          pulse && 'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
        )}
      />
      {pulse && (
        <span
          className={clsx('relative inline-flex rounded-full', colorMap[status], sizeMap[size])}
        />
      )}
    </span>
  )
}
