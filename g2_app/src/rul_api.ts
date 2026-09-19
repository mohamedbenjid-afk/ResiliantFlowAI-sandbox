/**
 * rul_api.ts — Client pour le microservice RUL live (api_rul.py)
 *
 * En dev  : appelle /rul-api/api/rul (proxied par Vite → localhost:8000)
 * En prod : appelle http://localhost:8000/api/rul directement
 */

const RUL_API_BASE = import.meta.env.DEV
  ? '/rul-api'
  : 'http://localhost:8000'

export interface LiveRUL {
  machine_id:     string
  scenario:       string
  scenario_label: string
  rul_jours:      number
  statut:         'Nominal' | 'Alerte' | 'Critique'
  temperature:    number
  vibration:      number
  pression:       number
  courant:        number
  tick:           number
  timestamp:      number
}

export async function fetchLiveRUL(): Promise<LiveRUL> {
  const resp = await fetch(`${RUL_API_BASE}/api/rul`, { signal: AbortSignal.timeout(8000) })
  if (!resp.ok) throw new Error(`RUL API error ${resp.status}`)
  return resp.json() as Promise<LiveRUL>
}

export interface AgentResponse {
  status:  'nominal' | 'loading' | 'ready'
  pages:   string[]
  loading: boolean
  error?:  string | null
  message?: string
}

export async function fetchPrescription(): Promise<AgentResponse> {
  const resp = await fetch(`${RUL_API_BASE}/api/agent`, { signal: AbortSignal.timeout(12000) })
  if (!resp.ok) throw new Error(`Agent API error ${resp.status}`)
  return resp.json() as Promise<AgentResponse>
}
