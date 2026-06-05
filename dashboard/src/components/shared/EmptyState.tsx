import { type LucideIcon, Inbox } from 'lucide-react'

interface EmptyStateProps {
  icon?: LucideIcon
  title?: string
  message: string
  action?: React.ReactNode
}

export function EmptyState({ icon: Icon = Inbox, title, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-14 h-14 rounded-full bg-gray-800 flex items-center justify-center mb-4">
        <Icon size={24} className="text-gray-500" />
      </div>
      {title && <h3 className="text-gray-300 font-medium text-base mb-1">{title}</h3>}
      <p className="text-gray-500 text-sm max-w-sm">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
