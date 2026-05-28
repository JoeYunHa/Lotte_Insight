'use client'

import { useEffect, useMemo, useRef, useState } from 'react'

import {
  getFanVoiceSseUrl,
  getFanVoiceStream,
  initFanVoiceSession,
  postFanVoiceReaction,
  postFanVoiceReport,
} from '@/lib/fan-voice-api'
import { FAN_VOICE_LIMITS, FAN_VOICE_POLLING } from '@/lib/fan-voice-constants'
import {
  createSchedulerState,
  scheduleNextBubble,
  type ActiveFanVoiceBubble,
  type SchedulerState,
} from '@/lib/fan-voice-lane-scheduler'
import { startFanVoiceSse } from '@/lib/fan-voice-stream-client'
import { readCleanMode, writeCleanMode } from '@/lib/fan-voice-storage'
import type { FanVoiceContextType, FanVoiceMessage } from '@/lib/fan-voice-types'

import { FanVoiceComposer } from './FanVoiceComposer'
import { FanVoiceHighlights } from './FanVoiceHighlights'
import { FanVoiceLane } from './FanVoiceLane'
import { FanVoiceToggle } from './FanVoiceToggle'

interface FanVoiceLayerProps {
  contextType: FanVoiceContextType
  contextId: string
}

function resolveLaneCount(width: number): number {
  if (width < 640) return FAN_VOICE_LIMITS.MOBILE_LANES
  if (width < 1024) return FAN_VOICE_LIMITS.TABLET_LANES
  return FAN_VOICE_LIMITS.DESKTOP_LANES
}

export function FanVoiceLayer({ contextType, contextId }: FanVoiceLayerProps) {
  const [streamMessages, setStreamMessages] = useState<FanVoiceMessage[]>([])
  const [activeBubbles, setActiveBubbles] = useState<ActiveFanVoiceBubble[]>([])
  const [cleanMode, setCleanMode] = useState(false)
  const [slowMode, setSlowMode] = useState(false)
  const [laneCount, setLaneCount] = useState(5)
  const schedulerRef = useRef<SchedulerState>(createSchedulerState(5))
  const reactingIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    setCleanMode(readCleanMode())
    const nextCount = resolveLaneCount(window.innerWidth)
    setLaneCount(nextCount)
    schedulerRef.current = createSchedulerState(nextCount)

    function handleResize() {
      const count = resolveLaneCount(window.innerWidth)
      setLaneCount((prev) => {
        if (prev === count) return prev
        schedulerRef.current = createSchedulerState(count)
        return count
      })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    let cancelled = false
    let stopSse: (() => void) | null = null
    let startedFallbackPolling = false

    async function runPollingFallback() {
      if (startedFallbackPolling) return
      startedFallbackPolling = true
      while (!cancelled) {
        try {
          const stream = await getFanVoiceStream({
            contextType,
            contextId,
            limit: 50,
          })
          if (!cancelled) {
            setStreamMessages(stream.messages)
            setSlowMode(stream.slow_mode)
          }
          const waitMs = stream.slow_mode
            ? FAN_VOICE_POLLING.SLOW_MODE_INTERVAL_MS
            : FAN_VOICE_POLLING.DEFAULT_INTERVAL_MS
          await new Promise((resolve) => setTimeout(resolve, waitMs))
        } catch {
          await new Promise((resolve) => setTimeout(resolve, FAN_VOICE_POLLING.ERROR_RETRY_MS))
        }
      }
    }

    async function bootstrapAndSubscribe() {
      try {
        await initFanVoiceSession()
      } catch {
        // keep going; stream endpoint and message endpoints can still recover
      }

      if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
        runPollingFallback()
        return
      }

      try {
        const url = getFanVoiceSseUrl({
          contextType,
          contextId,
          limit: 50,
        })
        stopSse = startFanVoiceSse({
          url,
          onStream(payload) {
            if (cancelled) return
            if (Array.isArray(payload.messages)) setStreamMessages(payload.messages)
            if (typeof payload.slow_mode === 'boolean') setSlowMode(payload.slow_mode)
          },
          onFallback() {
            if (cancelled) return
            runPollingFallback()
          },
        })
      } catch {
        runPollingFallback()
      }
    }

    bootstrapAndSubscribe()
    return () => {
      cancelled = true
      stopSse?.()
      stopSse = null
    }
  }, [contextType, contextId])

  useEffect(() => {
    if (cleanMode) return
    const timer = window.setInterval(() => {
      setActiveBubbles((prev) => {
        const next = prev.slice()
        const candidate = scheduleNextBubble(
          streamMessages,
          next,
          schedulerRef.current,
          Date.now()
        )
        if (!candidate) return prev
        next.push(candidate)
        window.setTimeout(() => {
          setActiveBubbles((current) => current.filter((item) => item.localId !== candidate.localId))
        }, candidate.durationSec * 1000)
        return next
      })
    }, 900)
    return () => window.clearInterval(timer)
  }, [cleanMode, streamMessages])

  const laneBubbles = useMemo(() => {
    const grouped: ActiveFanVoiceBubble[][] = Array.from({ length: laneCount }, () => [])
    for (const bubble of activeBubbles) {
      if (bubble.lane < grouped.length) grouped[bubble.lane].push(bubble)
    }
    return grouped
  }, [activeBubbles, laneCount])

  function toggleCleanMode(next: boolean) {
    setCleanMode(next)
    writeCleanMode(next)
    if (next) setActiveBubbles([])
  }

  async function handleReact(messageId: string) {
    if (reactingIdsRef.current.has(messageId)) return
    reactingIdsRef.current.add(messageId)
    setStreamMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, reaction_count: msg.reaction_count + 1 } : msg
      )
    )
    try {
      const res = await postFanVoiceReaction({ message_id: messageId, reaction_type: 'like' })
      setStreamMessages((prev) =>
        prev.map((msg) => (msg.id === messageId ? { ...msg, reaction_count: res.reaction_count } : msg))
      )
    } catch {
      setStreamMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId ? { ...msg, reaction_count: Math.max(0, msg.reaction_count - 1) } : msg
        )
      )
    } finally {
      reactingIdsRef.current.delete(messageId)
    }
  }

  async function handleReport(messageId: string) {
    const previous = streamMessages
    setStreamMessages((prev) => prev.filter((msg) => msg.id !== messageId))
    try {
      await postFanVoiceReport({ message_id: messageId, reason: 'spam' })
    } catch {
      setStreamMessages(previous)
    }
  }

  return (
    <section className="fan-voice-shell mb-8">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--muted)' }}>
          Fan Voice {slowMode ? '(Slow Mode)' : ''}
        </p>
        <FanVoiceToggle cleanMode={cleanMode} onToggle={toggleCleanMode} />
      </div>

      <FanVoiceComposer
        contextType={contextType}
        contextId={contextId}
        disabled={slowMode}
        onSubmitted={() => {
          // next poll will pick up the latest message
        }}
      />

      <FanVoiceHighlights messages={streamMessages} />

      {!cleanMode ? (
        <div className="fan-voice-overlay mt-3" style={{ height: laneCount * 42 + (laneCount - 1) * 8 }}>
          {laneBubbles.map((bubbles, laneIndex) => (
            <FanVoiceLane
              key={laneIndex}
              laneIndex={laneIndex}
              bubbles={bubbles}
              onReact={handleReact}
              onReport={handleReport}
            />
          ))}
        </div>
      ) : null}
    </section>
  )
}
