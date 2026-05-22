// DB schema-aligned types.
// Field names mirror the Supabase table columns exactly so that
// API responses can be returned as-is without remapping.

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

// articles + article_labels (primary) joined
export interface Article {
  id: string
  title: string
  source_name: string
  source_url: string
  published_at: string          // ISO 8601 datetime (UTC)
  author_name?: string | null
  event_summary?: string | null // KoBART output — null until summarizer runs
  primary_label?: LabelKey | null
  lotte_stance?: LotteStance | null
  key_players?: string[] | null  // player names from KoBART key_players field
  confidence?: number | null
  article_players?: Array<{     // Supabase join: article_players(player_id, players(name))
    player_id: number
    players: { name: string } | null
  }> | null
}

// players table
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

// player_stats_daily table
export interface PlayerStatDaily {
  player_id: number
  date: string                   // 'YYYY-MM-DD'
  avg?: number | null
  ops?: number | null
  era?: number | null
  raw_stats: Record<string, unknown>
}

// team_daily_report table
export interface TeamDailyReport {
  id: string
  date: string                   // 'YYYY-MM-DD'
  issue_summary: string
  article_count: number
  top_labels: LabelKey[]
}

// player_daily_report table + player name join
export interface PlayerDailyReport {
  id: string
  player_id: string
  date: string                   // 'YYYY-MM-DD'
  insight: string
  stat_snapshot: Partial<{ avg: number; ops: number; era: number }>
}

// top-mentioned player derived from article_players aggregation
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
  result: '승' | '패' | '무' | null
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
