import { describe, expect, it, vi } from 'vitest'

import { startFanVoiceSse } from '@/lib/fan-voice-stream-client'

class MockEventSource {
  static instances: MockEventSource[] = []
  listeners = new Map<string, Array<(event: { data: string }) => void>>()
  closed = false

  constructor(public readonly _url: string, public readonly _init?: { withCredentials?: boolean }) {
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, callback: (event: { data: string }) => void) {
    const callbacks = this.listeners.get(type) ?? []
    callbacks.push(callback)
    this.listeners.set(type, callbacks)
  }

  emit(type: string, data = '{}') {
    for (const callback of this.listeners.get(type) ?? []) {
      callback({ data })
    }
  }

  close() {
    this.closed = true
  }
}

describe('fan voice SSE client', () => {
  it('falls back when EventSource is unavailable', () => {
    const original = (globalThis as { EventSource?: unknown }).EventSource
    delete (globalThis as { EventSource?: unknown }).EventSource
    const onFallback = vi.fn()

    const stop = startFanVoiceSse({
      url: '/fan-voice/stream/sse',
      onStream: vi.fn(),
      onFallback,
    })
    stop()

    expect(onFallback).toHaveBeenCalledTimes(1)
    ;(globalThis as { EventSource?: unknown }).EventSource = original
  })

  it('applies slow_mode payload from stream event', () => {
    ;(globalThis as { EventSource?: unknown }).EventSource = MockEventSource
    const onStream = vi.fn()
    const onFallback = vi.fn()

    const stop = startFanVoiceSse({
      url: '/fan-voice/stream/sse',
      onStream,
      onFallback,
    })
    const instance = MockEventSource.instances.at(-1)
    expect(instance).toBeTruthy()
    instance?.emit('stream', JSON.stringify({ messages: [], slow_mode: true }))
    stop()

    expect(onStream).toHaveBeenCalledWith(
      expect.objectContaining({
        slow_mode: true,
      })
    )
    expect(onFallback).not.toHaveBeenCalled()
  })

  it('triggers fallback once on SSE error (reconnect handoff)', () => {
    ;(globalThis as { EventSource?: unknown }).EventSource = MockEventSource
    const onFallback = vi.fn()

    startFanVoiceSse({
      url: '/fan-voice/stream/sse',
      onStream: vi.fn(),
      onFallback,
    })
    const instance = MockEventSource.instances.at(-1)
    expect(instance).toBeTruthy()

    instance?.emit('error')
    instance?.emit('error')

    expect(onFallback).toHaveBeenCalledTimes(1)
    expect(instance?.closed).toBe(true)
  })
})
