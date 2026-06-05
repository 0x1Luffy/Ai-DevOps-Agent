import { format } from 'date-fns'
import { useStore } from '../../store'
import type { ActivityEvent } from '../../types'
import clsx from 'clsx'
import { type LucideIcon, Search, Wrench, CheckCircle, AlertOctagon, RefreshCw, GitBranch, Clock } from 'lucide-react'
import { EmptyState } from '../shared/EmptyState'

const eventConfig: Record<
  ActivityEvent['type'],
  { icon: LucideIcon; color: string; bg: string }
> = {
  detected: { icon: Search, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  fixing: { icon: Wrench, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  fixed: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/10' },
  escalated: { icon: AlertOctagon, color: 'text-red-400', bg: 'bg-red-500/10' },
  retried: { icon: RefreshCw, color: 'text-purple-400', bg: 'bg-purple-500/10' },
  jenkins_failure: { icon: GitBranch, color: 'text-orange-400', bg: 'bg-orange-500/10' },
  approval_needed: { icon: Clock, color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
}

interface ActivityEntryProps {
  event: ActivityEvent
  isNew: boolean
}

function ActivityEntry({ event, isNew }: ActivityEntryProps) {
  const cfg = eventConfig[event.type] ?? eventConfig.detected
  const IconComponent: LucideIcon = cfg.icon

  return (
    <div
      className={clsx(
        'flex items-start gap-3 py-2.5 px-3 rounded-lg transition-all duration-300',
        isNew ? 'bg-indigo-500/5 border border-indigo-500/20' : 'hover:bg-gray-800/50',
      )}
    >
      <div className={clsx('w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5', cfg.bg)}>
        <IconComponent size={13} className={cfg.color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-gray-300 text-sm leading-snug">{event.description}</p>
        {(event.resourceName || event.namespace) && (
          <p className="text-gray-600 text-xs mt-0.5">
            {[event.namespace, event.resourceName].filter(Boolean).join(' / ')}
          </p>
        )}
      </div>
      <span className="text-gray-600 text-xs tabular-nums shrink-0 mt-0.5">
        {format(new Date(event.timestamp), 'HH:mm:ss')}
      </span>
    </div>
  )
}

export function ActivityFeed() {
  const events = useStore((s) => s.activityFeed)

  if (!events.length) {
    return (
      <EmptyState
        icon={Search}
        title="No activity yet"
        message="Live events will appear here as the agent detects and fixes incidents."
      />
    )
  }

  return (
    <div className="space-y-1 max-h-80 overflow-y-auto pr-1">
      {events.slice(0, 20).map((event, idx) => (
        <ActivityEntry key={event.id} event={event} isNew={idx === 0} />
      ))}
    </div>
  )
}
