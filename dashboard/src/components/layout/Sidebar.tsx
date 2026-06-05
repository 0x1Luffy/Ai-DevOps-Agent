import { NavLink } from 'react-router-dom'
import {
  Bot,
  LayoutDashboard,
  AlertTriangle,
  Server,
  GitBranch,
  History,
  Settings,
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { to: '/cluster', label: 'Cluster', icon: Server },
  { to: '/jenkins', label: 'Jenkins', icon: GitBranch },
  { to: '/fixes', label: 'Fix History', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="w-60 min-h-screen bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-800">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
          <Bot size={18} className="text-white" />
        </div>
        <div>
          <span className="font-semibold text-white text-sm">AutoPilot</span>
          <p className="text-gray-500 text-xs leading-none mt-0.5">DevOps Agent</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-600/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800',
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-800">
        <p className="text-gray-600 text-xs">v1.0.0</p>
      </div>
    </aside>
  )
}
