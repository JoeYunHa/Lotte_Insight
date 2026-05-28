import { describe, expect, it } from 'vitest'

import {
  createSchedulerState,
  scheduleNextBubble,
  type ActiveFanVoiceBubble,
} from '@/lib/fan-voice-lane-scheduler'
import type { FanVoiceMessage } from '@/lib/fan-voice-types'

function makeMessage(id: string, alias: string, text: string): FanVoiceMessage {
  return {
    id,
    context_type: 'home',
    context_id: 'today',
    message: text,
    emotion_tag: null,
    topic_tag: null,
    session_alias: alias,
    player_id: null,
    cluster_id: null,
    game_date: null,
    reaction_count: 0,
    report_count: 0,
    is_highlighted: false,
    display_seconds: 10,
    created_at: '2026-05-28T00:00:00+00:00',
  }
}

describe('fan voice lane scheduler', () => {
  it('does not return bubble when active limit reached', () => {
    const state = createSchedulerState(3)
    const messages = [makeMessage('1', 'A', 'hello')]
    const active = new Array(12).fill(0).map(
      (_, i) =>
        ({
          localId: `x${i}`,
          lane: 0,
          message: messages[0],
          durationSec: 10,
          createdAtMs: 0,
        }) as ActiveFanVoiceBubble
    )
    const next = scheduleNextBubble(messages, active, state, Date.now())
    expect(next).toBeNull()
  })

  it('avoids consecutive same alias when possible', () => {
    const state = createSchedulerState(3)
    const now = Date.now() + 5000
    const messages = [
      makeMessage('1', 'A', 'first'),
      makeMessage('2', 'A', 'second'),
      makeMessage('3', 'B', 'third'),
    ]
    const first = scheduleNextBubble(messages, [], state, now)
    expect(first).not.toBeNull()
    const second = scheduleNextBubble(messages, [], state, now + 2000)
    expect(second).not.toBeNull()
    expect(second?.message.session_alias).not.toBe(first?.message.session_alias)
  })
})
