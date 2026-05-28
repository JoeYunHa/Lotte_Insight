import type {
  FanVoiceContextType,
  FanVoiceMessage,
  FanVoiceSessionResponse,
  FanVoiceStreamResponse,
  FanVoiceEmotion,
  FanVoiceTopicTag,
} from './fan-voice-types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''
const FETCH_OPTIONS: RequestInit = {
  next: { revalidate: 0 },
  credentials: 'include',
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function initFanVoiceSession(): Promise<FanVoiceSessionResponse> {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const res = await fetch(`${API_BASE}/fan-voice/session`, {
    ...FETCH_OPTIONS,
    method: 'POST',
  })
  return parseJson<FanVoiceSessionResponse>(res)
}

export async function getFanVoiceStream(params: {
  contextType: FanVoiceContextType
  contextId: string
  limit?: number
}): Promise<FanVoiceStreamResponse> {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const qs = new URLSearchParams({
    context_type: params.contextType,
    context_id: params.contextId,
  })
  if (params.limit != null) qs.set('limit', String(params.limit))
  const res = await fetch(`${API_BASE}/fan-voice/stream?${qs.toString()}`, FETCH_OPTIONS)
  return parseJson<FanVoiceStreamResponse>(res)
}

export function getFanVoiceSseUrl(params: {
  contextType: FanVoiceContextType
  contextId: string
  limit?: number
}): string {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const qs = new URLSearchParams({
    context_type: params.contextType,
    context_id: params.contextId,
  })
  if (params.limit != null) qs.set('limit', String(params.limit))
  return `${API_BASE}/fan-voice/stream/sse?${qs.toString()}`
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
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const res = await fetch(`${API_BASE}/fan-voice/messages`, {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return parseJson<FanVoiceMessage>(res)
}

export async function postFanVoiceReaction(input: {
  message_id: string
  reaction_type: 'like' | 'fire' | 'agree'
}): Promise<{ ok: true; reaction_count: number }> {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const res = await fetch(`${API_BASE}/fan-voice/reactions`, {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return parseJson<{ ok: true; reaction_count: number }>(res)
}

export async function postFanVoiceReport(input: {
  message_id: string
  reason: 'abuse' | 'spam' | 'hate' | 'other'
}): Promise<{ ok: true; report_count: number }> {
  if (!API_BASE) throw new Error('NEXT_PUBLIC_API_URL is not configured')
  const res = await fetch(`${API_BASE}/fan-voice/reports`, {
    ...FETCH_OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return parseJson<{ ok: true; report_count: number }>(res)
}
