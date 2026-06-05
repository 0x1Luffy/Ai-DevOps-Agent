import { type LucideIcon, AlertOctagon, AlertTriangle, Info } from 'lucide-react'
import clsx from 'clsx'
import type { Severity } from '../../types'

interface SeverityBadgeProps {
  severity: Severity
  size?: 'sm' | 'md'
}

const config: Record<Severity, { label: string; className: string; icon: LucideIcon }> = {
  CRITICAL: {
    label: 'CRITICAL',
    className: 'bg-red-500/15 text-red-400 border-red-500/30',
    icon: AlertOctagon,
  },
  HIGH: {
    label: 'HIGH',
    className: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    icon: AlertTriangle,
  },
  MEDIUM: {
    label: 'MEDIUM',
    className: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    icon: AlertTriangle,
  },
  LOW: {
    label: 'LOW',
    className: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    icon: Info,
  },
}

export function SeverityBadge({ severity, size = 'md' }: SeverityBadgeProps) {
  const cfg = config[severity] ?? config.LOW
  const IconComponent: LucideIcon = cfg.icon

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 font-medium rounded border',
        cfg.className,
        size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2 py-1',
      )}
    >
      <IconComponent size={size === 'sm' ? 10 : 12} />
      {cfg.label}
    </span>
  )
}
