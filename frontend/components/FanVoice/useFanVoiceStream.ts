"use client";

import { useEffect, useState } from "react";

import {
  getFanVoiceSseUrl,
  getFanVoiceStream,
  initFanVoiceSession,
} from "@/lib/fan-voice/fan-voice-api";
import { FAN_VOICE_POLLING } from "@/lib/fan-voice/fan-voice-constants";
import { startFanVoiceSse } from "@/lib/fan-voice/fan-voice-stream-client";
import { hasApiBase } from "@/lib/http-client";
import type {
  FanVoiceContextType,
  FanVoiceMessage,
} from "@/lib/fan-voice/fan-voice-types";

interface UseFanVoiceStreamProps {
  contextType: FanVoiceContextType;
  contextId: string;
  limit?: number;
}

export function useFanVoiceStream({
  contextType,
  contextId,
  limit = 50,
}: UseFanVoiceStreamProps) {
  const [streamMessages, setStreamMessages] = useState<FanVoiceMessage[]>([]);
  const [slowMode, setSlowMode] = useState(false);
  const [fanVoiceAvailable, setFanVoiceAvailable] = useState(true);

  useEffect(() => {
    if (!hasApiBase()) {
      setFanVoiceAvailable(false);
      return;
    }

    let cancelled = false;
    let stopSse: (() => void) | null = null;
    let startedFallbackPolling = false;

    async function runPollingFallback() {
      if (startedFallbackPolling) return;
      startedFallbackPolling = true;
      while (!cancelled) {
        try {
          const stream = await getFanVoiceStream({
            contextType,
            contextId,
            limit,
          });
          if (!cancelled) {
            setStreamMessages(stream.messages);
            setSlowMode(stream.slow_mode);
          }
          const waitMs = stream.slow_mode
            ? FAN_VOICE_POLLING.SLOW_MODE_INTERVAL_MS
            : FAN_VOICE_POLLING.DEFAULT_INTERVAL_MS;
          await new Promise((resolve) => setTimeout(resolve, waitMs));
        } catch (error) {
          setFanVoiceAvailable(false);
          await new Promise((resolve) =>
            setTimeout(resolve, FAN_VOICE_POLLING.ERROR_RETRY_MS),
          );
          return;
        }
      }
    }

    async function bootstrapAndSubscribe() {
      try {
        await initFanVoiceSession();
        setFanVoiceAvailable(true);
      } catch {
        setFanVoiceAvailable(false);
        return;
      }

      if (typeof window === "undefined" || typeof EventSource === "undefined") {
        runPollingFallback();
        return;
      }
      if (cancelled) return;

      try {
        const url = getFanVoiceSseUrl({ contextType, contextId, limit });
        stopSse = startFanVoiceSse({
          url,
          onStream(payload) {
            if (cancelled) return;
            if (Array.isArray(payload.messages)) {
              setStreamMessages(payload.messages);
            }
            if (typeof payload.slow_mode === "boolean") {
              setSlowMode(payload.slow_mode);
            }
          },
          onFallback() {
            if (cancelled) return;
            runPollingFallback();
          },
        });
      } catch (error) {
        runPollingFallback();
      }
    }

    bootstrapAndSubscribe();
    return () => {
      cancelled = true;
      stopSse?.();
      stopSse = null;
    };
  }, [contextId, contextType, limit]);

  return { streamMessages, setStreamMessages, slowMode, fanVoiceAvailable };
}
