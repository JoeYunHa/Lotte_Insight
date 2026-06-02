export type FanVoiceContextType = 'home' | 'player' | 'topic' | 'game' | 'label'

export type FanVoiceEmotion = 'CHEER' | 'EXPECT' | 'FRUSTRATED' | 'MOVED' | 'ANGRY'

export type FanVoiceTopicTag =
  | 'TODAY_MVP'
  | 'BULLPEN'
  | 'LINEUP'
  | 'DEFENSE'
  | 'UMPIRE'
  | 'MANAGER'

export interface FanVoiceMessage {
  id: string
  context_type: FanVoiceContextType
  context_id: string
  message: string
  emotion_tag: FanVoiceEmotion | null
  topic_tag: FanVoiceTopicTag | null
  session_alias: string
  player_id: number | null
  cluster_id: string | null
  game_date: string | null
  reaction_count: number
  report_count: number
  is_highlighted: boolean
  display_seconds: number
  created_at: string
}

export interface FanVoiceStreamResponse {
  messages: FanVoiceMessage[]
  slow_mode: boolean
  presence_count: number
  emotion_summary: Record<string, number>
  next_poll_after_ms: number
}

export interface FanVoiceSessionResponse {
  session_alias: string
  slow_mode: boolean
  blocked: boolean
  session_token: string
}
