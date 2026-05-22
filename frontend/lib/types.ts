export type LabelKey =
  | 'MATCH_RELATED'
  | 'INJURY_ROSTER'
  | 'TRANSACTION_CONTRACT'
  | 'PERFORMANCE_ANALYSIS'
  | 'INTERVIEW'
  | 'CLUB_OPERATION'
  | 'ETC'

export type LotteStance = 'positive' | 'negative' | 'neutral'
export type GameResult = '승' | '패' | '무'
export type PlayerStatus = 'active' | '1군' | '2군' | '말소'

export interface Article {
  id: string
  title: string
  source_name: string
  source_url: string
  published_at: string
  author_name?: string | null
  event_summary?: string | null
  primary_label?: LabelKey | null
  lotte_stance?: LotteStance | null
  key_players?: string[] | null
  confidence?: number | null
  article_players?: Array<{
    player_id: number
    players: { name: string } | null
  }> | null
}

export interface Player {
  id: string
  name: string
  name_variants?: string[]
  position: string
  status: PlayerStatus
  number?: string | null
}

export interface PlayerDetail extends Player {
  stats?: PlayerStatDaily[]
}

export interface PlayerStatDaily {
  player_id: number
  date: string
  avg?: number | null
  ops?: number | null
  era?: number | null
  raw_stats: Record<string, unknown>
}

export interface TeamDailyReport {
  id: string
  date: string
  issue_summary: string
  article_count: number
  top_labels: LabelKey[]
}

export interface PlayerDailyReport {
  id: string
  player_id: string
  date: string
  insight: string
  stat_snapshot: Partial<{ avg: number; ops: number; era: number }>
}

export interface PlayerMention {
  player: Pick<Player, 'id' | 'name' | 'position'>
  mention_count: number
}

export interface GameContext {
  date: string
  opponent: string
  venue: string
  home_away: '홈' | '원정'
  game_time: string | null
  result: GameResult | null
  score: string | null
}

export interface SentimentData {
  positive: number
  neutral: number
  negative: number
  analyzed: number
}

export interface HomeReport {
  date: string
  article_count: number
  label_counts: Record<LabelKey, number>
  sentiment: SentimentData
  lead_label: LabelKey | null
  lead_summary: string | null
  lead_key_players: string[]
  top_players: PlayerMention[]
  team_report: TeamDailyReport | null
  game_context: GameContext | null
}
