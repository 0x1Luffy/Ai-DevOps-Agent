import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { format } from 'date-fns'
import { Wifi, WifiOff } from 'lucide-react'
import { useStore } from '../../store'
import clsx from 'clsx'

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/incidents': 'Incidents',
  '/cluster': 'Cluster Health',
  '/jenkins': 'Jenkins Pipelines',
  '/fixes': 'Fix History',
  '/settings': 'Settings',
}

export function Header() {
  const location = useLocation()
  const wsConnected = useStore((s) => s.wsConnected)
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  const title =
    pageTitles[location.pathname] ??
    (location.pathname.startsWith('/incidents/') ? 'Incident Detail' : 'AutoPilot')

  return (
    <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6 shrink-0">
      <h1 className="text-white font-semibold text-base">{title}</h1>

      <div className="flex items-center gap-4">
        {/* WebSocket status */}
        <div
          className={clsx(
            'flex items-center gap-2 text-xs font-medium px-2.5 py-1 rounded-full border',
            wsConnected
              ? 'text-green-400 border-green-600/40 bg-green-500/10'
              : 'text-gray-500 border-gray-700 bg-gray-800',
          )}
        >
          {wsConnected ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              Live
            </>
          ) : (
            <>
              <WifiOff size={12} />
              Reconnecting...
            </>
          )}
        </div>

        {/* Time */}
        <span className="text-gray-500 text-xs tabular-nums">
          {format(now, 'HH:mm:ss')}
        </span>
      </div>
    </header>
  )
}
