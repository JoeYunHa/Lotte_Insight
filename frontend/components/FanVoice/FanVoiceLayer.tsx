"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  postFanVoiceReaction,
  postFanVoiceReport,
} from "@/lib/fan-voice/fan-voice-api";
import { FAN_VOICE_LIMITS } from "@/lib/fan-voice/fan-voice-constants";
import {
  createSchedulerState,
  scheduleNextBubble,
  type ActiveFanVoiceBubble,
  type SchedulerState,
} from "@/lib/fan-voice/fan-voice-lane-scheduler";
import type {
  FanVoiceContextType,
  FanVoiceMessage,
} from "@/lib/fan-voice/fan-voice-types";

import { FanVoiceComposer } from "./FanVoiceComposer";
import { FanVoiceLane } from "./FanVoiceLane";
import { FanVoiceToggle } from "./FanVoiceToggle";
import { useFanVoiceStream } from "./useFanVoiceStream";

interface FanVoiceLayerProps {
  contextType: FanVoiceContextType;
  contextId: string;
}

function resolveLaneCount(width: number): number {
  if (width < 640) return FAN_VOICE_LIMITS.MOBILE_LANES;
  if (width < 1024) return FAN_VOICE_LIMITS.TABLET_LANES;
  return FAN_VOICE_LIMITS.DESKTOP_LANES;
}

const DEFAULT_LANE_COUNT = FAN_VOICE_LIMITS.DESKTOP_LANES;

export function FanVoiceLayer({ contextType, contextId }: FanVoiceLayerProps) {
  const { streamMessages, setStreamMessages, slowMode, fanVoiceAvailable } =
    useFanVoiceStream({
      contextType,
      contextId,
    });
  const [activeBubbles, setActiveBubbles] = useState<ActiveFanVoiceBubble[]>(
    [],
  );
  const [chatOpen, setChatOpen] = useState(false);
  const [laneCount, setLaneCount] = useState<number>(DEFAULT_LANE_COUNT);
  const schedulerRef = useRef<SchedulerState>(
    createSchedulerState(DEFAULT_LANE_COUNT),
  );
  const reactingIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    function handleResize() {
      const count = resolveLaneCount(window.innerWidth);
      setLaneCount((prev) => {
        if (prev === count) return prev;
        schedulerRef.current = createSchedulerState(count);
        return count;
      });
    }

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (chatOpen) return;
    const timer = window.setInterval(() => {
      setActiveBubbles((prev) => {
        const next = prev.slice();
        const candidate = scheduleNextBubble(
          streamMessages,
          next,
          schedulerRef.current,
          Date.now(),
        );
        if (!candidate) return prev;
        next.push(candidate);
        window.setTimeout(() => {
          setActiveBubbles((current) =>
            current.filter((item) => item.localId !== candidate.localId),
          );
        }, candidate.durationSec * 1000);
        return next;
      });
    }, 900);
    return () => window.clearInterval(timer);
  }, [chatOpen, streamMessages]);

  const laneBubbles = useMemo(() => {
    const grouped: ActiveFanVoiceBubble[][] = Array.from(
      { length: laneCount },
      () => [],
    );
    for (const bubble of activeBubbles) {
      if (bubble.lane < grouped.length) grouped[bubble.lane].push(bubble);
    }
    return grouped;
  }, [activeBubbles, laneCount]);

  async function handleReact(messageId: string) {
    if (reactingIdsRef.current.has(messageId)) return;
    reactingIdsRef.current.add(messageId);
    let prevCount = 0;
    setStreamMessages((prev) =>
      prev.map((msg) => {
        if (msg.id === messageId) {
          prevCount = msg.reaction_count;
          return { ...msg, reaction_count: prevCount + 1 };
        }
        return msg;
      }),
    );
    try {
      const res = await postFanVoiceReaction({
        message_id: messageId,
        reaction_type: "like",
      });
      setStreamMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? { ...msg, reaction_count: res.reaction_count }
            : msg,
        ),
      );
    } catch {
      setStreamMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId ? { ...msg, reaction_count: prevCount } : msg,
        ),
      );
    } finally {
      reactingIdsRef.current.delete(messageId);
    }
  }

  async function handleReport(messageId: string) {
    let removedMsg: FanVoiceMessage | undefined;
    setStreamMessages((prev) => {
      removedMsg = prev.find((msg) => msg.id === messageId);
      return prev.filter((msg) => msg.id !== messageId);
    });
    try {
      await postFanVoiceReport({ message_id: messageId, reason: "spam" });
    } catch {
      if (removedMsg) {
        const captured = removedMsg;
        setStreamMessages((prev) => [...prev, captured]);
      }
    }
  }

  function toggleChat(next: boolean) {
    setChatOpen(next);
    if (next) setActiveBubbles([]);
  }

  return (
    <>
      {fanVoiceAvailable && !chatOpen ? (
        <div className="fan-voice-overlay">
          {laneBubbles.map((bubbles, laneIndex) => (
            <FanVoiceLane
              key={laneIndex}
              bubbles={bubbles}
              onReact={handleReact}
              onReport={handleReport}
            />
          ))}
        </div>
      ) : null}

      {chatOpen ? (
        <div className="fan-voice-chat-panel">
          {!fanVoiceAvailable ? (
            <p className="mb-2 text-xs" style={{ color: "var(--dim)" }}>
              Fan voice feed is temporarily unavailable.
            </p>
          ) : null}
          <FanVoiceComposer
            contextType={contextType}
            contextId={contextId}
            disabled={slowMode || !fanVoiceAvailable}
            onSubmitted={() => {}}
          />
        </div>
      ) : null}

      <FanVoiceToggle open={chatOpen} onToggle={toggleChat} />
    </>
  );
}
