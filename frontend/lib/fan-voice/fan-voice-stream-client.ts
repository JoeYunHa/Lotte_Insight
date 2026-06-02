import type { FanVoiceMessage } from './fan-voice-types'

export interface FanVoiceStreamPayload {
  messages?: FanVoiceMessage[]
  slow_mode?: boolean
}

interface StartFanVoiceSseOptions {
  url: string
  onStream: (payload: FanVoiceStreamPayload) => void
  onFallback: () => void
}

export function startFanVoiceSse(options: StartFanVoiceSseOptions): () => void {
  if (typeof EventSource === 'undefined') {
    options.onFallback()
    return () => {}
  }

  const source = new EventSource(options.url, { withCredentials: true })
  let fallbackTriggered = false

  source.addEventListener('stream', (event) => {
    try {
      const payload = JSON.parse((event as MessageEvent<string>).data) as FanVoiceStreamPayload
      options.onStream(payload)
    } catch (error) {
      console.error('[fan-voice] malformed SSE payload', error)
    }
  })

  source.addEventListener('error', () => {
    if (fallbackTriggered) return
    fallbackTriggered = true
    source.close()
    options.onFallback()
  })

  return () => {
    source.close()
  }
}
