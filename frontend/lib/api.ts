import type {
  Article,
  LabelKey,
  PlayerDailyReport,
  PlayerDetail,
  Player,
  TeamDailyReport,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

const FETCH_OPTIONS: RequestInit = { next: { revalidate: 300 } }

async function get<T>(path: string): Promise<T> {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const res = await fetch(`${API_BASE}${path}`, FETCH_OPTIONS)
  if (!res.ok) {
    throw new Error(`GET ${path} failed with HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function getOrNull<T>(path: string): Promise<T | null> {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const res = await fetch(`${API_BASE}${path}`, FETCH_OPTIONS)
  if (res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new Error(`GET ${path} failed with HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function getTeamReport(date: string): Promise<TeamDailyReport | null> {
  return getOrNull<TeamDailyReport>(`/reports/team/${date}`)
}

export async function getTeamReports(limit = 60): Promise<TeamDailyReport[]> {
  return get<TeamDailyReport[]>(`/reports/team?limit=${limit}`)
}

export async function getArticles(params: {
  date?: string
  label?: LabelKey
  player_id?: string
  limit?: number
  offset?: number
} = {}): Promise<Article[]> {
  const qs = new URLSearchParams()
  if (params.date) qs.set('article_date', params.date)
  if (params.label) qs.set('label', params.label)
  if (params.player_id) qs.set('player_id', params.player_id)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))

  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return get<Article[]>(`/articles${suffix}`)
}

export async function getPlayers(): Promise<Player[]> {
  return get<Player[]>('/players')
}

export async function getPlayer(id: string, statsDate?: string): Promise<PlayerDetail | null> {
  const qs = statsDate ? `?stats_date=${statsDate}` : ''
  return getOrNull<PlayerDetail>(`/players/${id}${qs}`)
}

export async function getPlayerReport(
  playerId: string,
  date: string
): Promise<PlayerDailyReport | null> {
  return getOrNull<PlayerDailyReport>(`/reports/players/${playerId}/${date}`)
}
