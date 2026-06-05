import { create } from 'zustand'
import type { DashboardSummary, ActivityEvent, Incident, AgentConfig } from '../types'

interface AppStore {
  summary: DashboardSummary | null
  setSummary: (s: DashboardSummary) => void
  activityFeed: ActivityEvent[]
  addActivity: (event: ActivityEvent) => void
  liveIncidentUpdates: Map<string, Partial<Incident>>
  updateIncident: (id: string, update: Partial<Incident>) => void
  wsConnected: boolean
  setWsConnected: (v: boolean) => void
  agentConfig: AgentConfig | null
  setAgentConfig: (c: AgentConfig) => void
}

export const useStore = create<AppStore>((set) => ({
  summary: null,
  setSummary: (summary) => set({ summary }),
  activityFeed: [],
  addActivity: (event) =>
    set((state) => ({
      activityFeed: [event, ...state.activityFeed].slice(0, 50),
    })),
  liveIncidentUpdates: new Map(),
  updateIncident: (id, update) =>
    set((state) => {
      const map = new Map(state.liveIncidentUpdates)
      map.set(id, { ...map.get(id), ...update })
      return { liveIncidentUpdates: map }
    }),
  wsConnected: false,
  setWsConnected: (wsConnected) => set({ wsConnected }),
  agentConfig: null,
  setAgentConfig: (agentConfig) => set({ agentConfig }),
}))
