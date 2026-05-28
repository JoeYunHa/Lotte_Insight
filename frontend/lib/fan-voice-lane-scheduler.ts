import { FAN_VOICE_ANIMATION, FAN_VOICE_LIMITS } from './fan-voice-constants'
import type { FanVoiceMessage } from './fan-voice-types'

export interface ActiveFanVoiceBubble {
  localId: string
  lane: number
  message: FanVoiceMessage
  durationSec: number
  createdAtMs: number
}

export interface SchedulerState {
  laneLastSpawnAtMs: number[]
  cursor: number
  lastSessionAlias: string | null
  recentMessageSignatures: string[]
}

export function createSchedulerState(laneCount: number): SchedulerState {
  return {
    laneLastSpawnAtMs: new Array(laneCount).fill(0),
    cursor: 0,
    lastSessionAlias: null,
    recentMessageSignatures: [],
  }
}

function computeDurationSec(message: string): number {
  const sec = FAN_VOICE_ANIMATION.MIN_DURATION_SEC + message.length * FAN_VOICE_ANIMATION.PER_CHAR_SEC
  return Math.max(FAN_VOICE_ANIMATION.MIN_DURATION_SEC, Math.min(FAN_VOICE_ANIMATION.MAX_DURATION_SEC, sec))
}

function pickLane(state: SchedulerState, nowMs: number): number | null {
  let candidate = -1
  let oldest = Number.POSITIVE_INFINITY
  for (let i = 0; i < state.laneLastSpawnAtMs.length; i += 1) {
    const last = state.laneLastSpawnAtMs[i]
    if (nowMs - last < FAN_VOICE_LIMITS.MIN_SPAWN_GAP_MS) continue
    if (last < oldest) {
      oldest = last
      candidate = i
    }
  }
  return candidate >= 0 ? candidate : null
}

function normalizeSignature(message: FanVoiceMessage): string {
  return `${message.session_alias}|${message.message.trim().toLowerCase()}`
}

function pickMessage(streamMessages: FanVoiceMessage[], state: SchedulerState): FanVoiceMessage {
  const total = streamMessages.length
  for (let i = 0; i < total; i += 1) {
    const idx = (state.cursor + i) % total
    const candidate = streamMessages[idx]
    const signature = normalizeSignature(candidate)
    const aliasRepeated = state.lastSessionAlias != null && state.lastSessionAlias === candidate.session_alias
    const duplicateText = state.recentMessageSignatures.includes(signature)
    if (!aliasRepeated && !duplicateText) {
      state.cursor = idx + 1
      return candidate
    }
  }
  const fallback = streamMessages[state.cursor % total]
  state.cursor += 1
  return fallback
}

export function scheduleNextBubble(
  streamMessages: FanVoiceMessage[],
  activeBubbles: ActiveFanVoiceBubble[],
  schedulerState: SchedulerState,
  nowMs: number
): ActiveFanVoiceBubble | null {
  if (!streamMessages.length) return null
  if (activeBubbles.length >= FAN_VOICE_LIMITS.MAX_VISIBLE_BUBBLES) return null

  const lane = pickLane(schedulerState, nowMs)
  if (lane == null) return null

  const message = pickMessage(streamMessages, schedulerState)
  schedulerState.laneLastSpawnAtMs[lane] = nowMs
  schedulerState.lastSessionAlias = message.session_alias
  const signature = normalizeSignature(message)
  schedulerState.recentMessageSignatures.push(signature)
  if (schedulerState.recentMessageSignatures.length > 20) {
    schedulerState.recentMessageSignatures.shift()
  }

  return {
    localId: `${message.id}-${nowMs}-${schedulerState.cursor}`,
    lane,
    message,
    durationSec: computeDurationSec(message.message),
    createdAtMs: nowMs,
  }
}
