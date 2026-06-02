import type {
  Article,
  HomeReport,
  LabelKey,
  PlayerDailyReport,
  PlayerDetail,
  Player,
  TeamDailyReport,
  TopicMapData,
} from './types'
import { requestJson, requestJsonOrNull } from './http-client'

const FETCH_OPTIONS: RequestInit = { next: { revalidate: 300 } }

export async function getTeamReport(date: string): Promise<TeamDailyReport | null> {
  return requestJsonOrNull<TeamDailyReport>(`/reports/team/${date}`, FETCH_OPTIONS)
}

export async function getTeamReports(limit = 60): Promise<TeamDailyReport[]> {
  return requestJson<TeamDailyReport[]>(`/reports/team?limit=${limit}`, FETCH_OPTIONS)
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
  return requestJson<Article[]>(`/articles${suffix}`, FETCH_OPTIONS)
}

export async function getPlayers(): Promise<Player[]> {
  return requestJson<Player[]>('/players', FETCH_OPTIONS)
}

export async function getPlayer(id: string, statsDate?: string): Promise<PlayerDetail | null> {
  const qs = statsDate ? `?stats_date=${statsDate}` : ''
  return requestJsonOrNull<PlayerDetail>(`/players/${id}${qs}`, FETCH_OPTIONS)
}

export async function getPlayerReport(
  playerId: string,
  date: string
): Promise<PlayerDailyReport | null> {
  return requestJsonOrNull<PlayerDailyReport>(
    `/reports/players/${playerId}/${date}`,
    FETCH_OPTIONS,
  )
}

export async function getHomeReport(date: string): Promise<HomeReport> {
  return requestJson<HomeReport>(`/reports/home?report_date=${date}`, FETCH_OPTIONS)
}

export async function getTopicMap(date: string): Promise<TopicMapData | null> {
  return requestJsonOrNull<TopicMapData>(`/topics?map_date=${date}`, FETCH_OPTIONS)
}
