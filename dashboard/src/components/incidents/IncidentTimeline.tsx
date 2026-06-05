import { useState } from 'react'
import { format } from 'date-fns'
import {
  type LucideIcon,
  Search,
  Brain,
  MessageSquare,
  CheckCircle,
  Wrench,
  Eye,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'
import type { TimelineEvent } from '../../types'

const typeConfig: Record<
  TimelineEvent['type'],
  { icon: LucideIcon; color: string; bg: string }
> = {
  detected: { icon: Search, color: 'text-blue-400', bg: 'bg-blue-500/20' },
  diagnosed: { icon: Brain, color: 'text-purple-400', bg: 'bg-purple-500/20' },
  approval_sent: { icon: MessageSquare, color: 'text-cyan-400', bg: 'bg-cyan-500/20' },
  approved: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/20' },
  fix_applied: { icon: Wrench, color: 'text-yellow-400', bg: 'bg-yellow-500/20' },
  verifying: { icon: Eye, color: 'text-indigo-400', bg: 'bg-indigo-500/20' },
  verified: { icon: ShieldCheck, color: 'text-green-400', bg: 'bg-green-500/20' },
  escalated: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/20' },
  failed: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/20' },
}

interface TimelineItemProps {
  event: TimelineEvent
  isLast: boolean
}

function TimelineItem({ event, isLast }: TimelineItemProps) {
  const [expanded, setExpanded] = useState(false)
  const cfg = typeConfig[event.type] ?? typeConfig.detected
  const IconComponent: LucideIcon = cfg.icon
  const hasDetails = event.details && Object.keys(event.details).length > 0

  return (
    <div className="flex gap-3">
      {/* Icon + connector */}
      <div className="flex flex-col items-center">
        <div className={clsx('w-7 h-7 rounded-full flex items-center justify-center shrink-0', cfg.bg)}>
          <IconComponent size={13} className={cfg.color} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-gray-700 mt-1" />}
      </div>

      {/* Content */}
      <div className={clsx('pb-5 flex-1 min-w-0', isLast && 'pb-0')}>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-gray-200 text-sm font-medium">{event.title}</p>
            <p className="text-gray-500 text-xs mt-0.5">{event.description}</p>
          </div>
          <span className="text-gray-600 text-xs tabular-nums shrink-0">
            {format(new Date(event.timestamp), 'HH:mm:ss')}
          </span>
        </div>

        {hasDetails && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 mt-1.5 transition-colors"
          >
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {expanded ? 'Hide details' : 'Show details'}
          </button>
        )}

        {expanded && event.details && (
          <pre className="mt-2 text-xs bg-gray-900 text-gray-400 p-3 rounded-lg overflow-x-auto border border-gray-700">
            {JSON.stringify(event.details, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

interface IncidentTimelineProps {
  events: TimelineEvent[]
}

export function IncidentTimeline({ events }: IncidentTimelineProps) {
  if (!events.length) {
    return <p className="text-gray-500 text-sm italic">No timeline events recorded.</p>
  }

  return (
    <div className="space-y-0">
      {events.map((event, idx) => (
        <TimelineItem key={`${event.timestamp}-${idx}`} event={event} isLast={idx === events.length - 1} />
      ))}
    </div>
  )
}
