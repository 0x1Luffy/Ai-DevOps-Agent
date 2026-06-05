import { useEffect, useRef, useState, useCallback } from 'react'
import { useStore } from '../store'
import type { Incident, ActivityEvent } from '../types'

interface WsEvent {
  type: 'new_incident' | 'fix_applied' | 'fix_verified' | 'jenkins_failure' | 'approval_needed'
  data: Record<string, unknown>
}

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:3001'
const MAX_BACKOFF_MS = 30_000
const CHANNELS = ['incidents', 'cluster', 'jenkins']

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [lastMessage, setLastMessage] = useState<WsEvent | null>(null)

  const { setWsConnected, addActivity, updateIncident } = useStore()

  const handleMessage = useCallback(
    (event: WsEvent) => {
      setLastMessage(event)

      switch (event.type) {
        case 'new_incident': {
          const incident = event.data as unknown as Incident
          const activity: ActivityEvent = {
            id: `ws-${Date.now()}`,
            timestamp: new Date().toISOString(),
            type: 'detected',
            description: `New incident detected: ${incident.problemType ?? 'Unknown'}`,
            resourceName: incident.resourceName,
            namespace: incident.namespace,
            severity: incident.severity,
          }
          addActivity(activity)
          break
        }
        case 'fix_applied': {
          const { incidentId, status } = event.data as { incidentId: string; status: string }
          updateIncident(incidentId, { status: status as Incident['status'] })
          const activity: ActivityEvent = {
            id: `ws-${Date.now()}`,
            timestamp: new Date().toISOString(),
            type: 'fixing',
            description: `Fix applied to incident ${incidentId}`,
          }
          addActivity(activity)
          break
        }
        case 'fix_verified': {
          const { incidentId, result } = event.data as { incidentId: string; result: string }
          const newStatus = result === 'fixed' ? 'fixed' : 'still_broken'
          updateIncident(incidentId, { status: newStatus as Incident['status'] })
          const activity: ActivityEvent = {
            id: `ws-${Date.now()}`,
            timestamp: new Date().toISOString(),
            type: result === 'fixed' ? 'fixed' : 'escalated',
            description: `Fix verified for incident ${incidentId}: ${result}`,
          }
          addActivity(activity)
          break
        }
        case 'jenkins_failure': {
          const { jobName, failureType } = event.data as { jobName: string; failureType: string }
          const activity: ActivityEvent = {
            id: `ws-${Date.now()}`,
            timestamp: new Date().toISOString(),
            type: 'jenkins_failure',
            description: `Jenkins build failed: ${jobName} (${failureType})`,
          }
          addActivity(activity)
          break
        }
        case 'approval_needed': {
          const { incidentId } = event.data as { incidentId: string }
          updateIncident(incidentId, { status: 'needs_approval' })
          const activity: ActivityEvent = {
            id: `ws-${Date.now()}`,
            timestamp: new Date().toISOString(),
            type: 'approval_needed',
            description: `Approval needed for incident ${incidentId}`,
          }
          addActivity(activity)
          break
        }
      }
    },
    [addActivity, updateIncident],
  )

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
        reconnectAttemptRef.current = 0
        ws.send(JSON.stringify({ type: 'subscribe', channels: CHANNELS }))
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data as string) as WsEvent
          handleMessage(parsed)
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        wsRef.current = null
        scheduleReconnect()
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      scheduleReconnect()
    }
  }, [handleMessage, setWsConnected]) // eslint-disable-line react-hooks/exhaustive-deps

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    const delay = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), MAX_BACKOFF_MS)
    reconnectAttemptRef.current += 1
    reconnectTimerRef.current = setTimeout(() => {
      connect()
    }, delay)
  }, [connect])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  const connected = useStore((s) => s.wsConnected)
  return { connected, lastMessage }
}
