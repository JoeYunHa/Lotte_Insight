import type {
  FanVoiceContextType,
  FanVoiceMessage,
  FanVoiceSessionResponse,
  FanVoiceStreamResponse,
  FanVoiceEmotion,
  FanVoiceTopicTag,
} from './fan-voice-types'
import { buildApiUrl, requestJson } from '../http-client'

const FETCH_OPTIONS: RequestInit = {
  next: { revalidate: 0 },
  credentials: 'include',
}

export async function initFanVoiceSession(): Promise<FanVoiceSessionResponse> {
  return requestJson<FanVoiceSessionResponse>('/fan-voice/session', {
    ...FETCH_OPTIONS,
    method: 'POST',
  }, 'POST')
}

export async function getFanVoiceStream(params: {
  contextType: FanVoiceContextType
  contextId: string
  limit?: number
}): Promise<FanVoiceStreamResponse> {
  const qs = new URLSearchParams({
    context_type: params.contextType,
    context_id: params.contextId,
  })
  if (params.limit != null) qs.set('limit', String(params.limit))
  return requestJson<FanVoiceStreamResponse>(
    `/fan-voice/stream?${qs.toString()}`,
    FETCH_OPTIONS,
  )
}

export function getFanVoiceSseUrl(params: {
  contextType: FanVoiceContextType
  contextId: string
  limit?: number
}): string {
  const qs = new URLSearchParams({
    context_type: params.contextType,
    context_id: params.contextId,
  })
  if (params.limit != null) qs.set('limit', String(params.limit))
  return buildApiUrl(`/fan-voice/stream/sse?${qs.toString()}`)
}

export async function postFanVoiceMessage(input: {
  context_type: FanVoiceContextType
  context_id: string
  message: string
  emotion_tag?: FanVoiceEmotion | null
  topic_tag?: FanVoiceTopicTag | null
  player_id?: number | null
  cluster_id?: string | null
  game_date?: string | null
}): Promise<FanVoiceMessage> {
  return requestJson<FanVoiceMessage>('/fan-voice/messages', {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, 'POST')
}

export async function postFanVoiceReaction(input: {
  message_id: string
  reaction_type: 'like' | 'fire' | 'agree'
}): Promise<{ ok: true; reaction_count: number }> {
  return requestJson<{ ok: true; reaction_count: number }>('/fan-voice/reactions', {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, 'POST')
}

export async function postFanVoiceReport(input: {
  message_id: string
  reason: 'abuse' | 'spam' | 'hate' | 'other'
}): Promise<{ ok: true; report_count: number }> {
  return requestJson<{ ok: true; report_count: number }>('/fan-voice/reports', {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, 'POST')
}
