'use client'

import { useState } from 'react'

import { postFanVoiceMessage } from '@/lib/fan-voice-api'
import type { FanVoiceContextType } from '@/lib/fan-voice-types'

interface FanVoiceComposerProps {
  contextType: FanVoiceContextType
  contextId: string
  disabled?: boolean
  onSubmitted?: () => void
}

const EMOTIONS = [
  { value: '', label: 'No Emotion' },
  { value: 'CHEER', label: 'Cheer' },
  { value: 'EXPECT', label: 'Expect' },
  { value: 'FRUSTRATED', label: 'Frustrated' },
  { value: 'MOVED', label: 'Moved' },
  { value: 'ANGRY', label: 'Angry' },
] as const

export function FanVoiceComposer({ contextType, contextId, disabled, onSubmitted }: FanVoiceComposerProps) {
  const [message, setMessage] = useState('')
  const [emotion, setEmotion] = useState<(typeof EMOTIONS)[number]['value']>('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = !disabled && !submitting && message.trim().length > 0 && message.trim().length <= 60

  async function submit() {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      await postFanVoiceMessage({
        context_type: contextType,
        context_id: contextId,
        message: message.trim(),
        emotion_tag: emotion || null,
      })
      setMessage('')
      setEmotion('')
      onSubmitted?.()
    } catch {
      setError('Failed to post message')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-2xl border p-2" style={{ borderColor: 'var(--border)', background: 'rgba(255,255,255,0.82)' }}>
      <select
        className="rounded-md border px-2 py-1 text-xs"
        style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        value={emotion}
        onChange={(e) => setEmotion(e.target.value as (typeof EMOTIONS)[number]['value'])}
        disabled={disabled || submitting}
      >
        {EMOTIONS.map((option) => (
          <option key={option.label} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={message}
        maxLength={60}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Share your fan voice..."
        className="min-w-[180px] flex-1 rounded-md border px-3 py-1.5 text-sm"
        style={{ borderColor: 'var(--border)', color: 'var(--text)', background: 'var(--surface)' }}
        disabled={disabled || submitting}
      />
      <button
        type="button"
        onClick={submit}
        disabled={!canSubmit}
        className="rounded-md px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50"
        style={{ background: 'var(--red)', color: '#fff' }}
      >
        Post
      </button>
      {error ? (
        <p className="basis-full text-xs" style={{ color: 'var(--loss)' }}>
          {error}
        </p>
      ) : null}
    </div>
  )
}
