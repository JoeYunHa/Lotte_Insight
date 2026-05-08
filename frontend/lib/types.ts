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

export type LotteStance = '긍정' | '부정' | '중립'
export type GameResult = '승' | '패' | '무'
export type PlayerStatus = '1군' | '2군' | '말소'

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
}

// players table
export interface Player {
  id: string
  name: string
  name_variants: string[]
  position: string
  status: PlayerStatus
  number?: string | null
}

// player_stats_daily table
export interface PlayerStatDaily {
  player_id: string
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
