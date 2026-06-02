"use client";

import type { ActiveFanVoiceBubble } from "@/lib/fan-voice/fan-voice-lane-scheduler";
import type { FanVoiceEmotion } from "@/lib/fan-voice/fan-voice-types";

const EMOTION_SYMBOL: Record<FanVoiceEmotion, string> = {
  CHEER: "📣",
  EXPECT: "⭐",
  FRUSTRATED: "😤",
  MOVED: "🥺",
  ANGRY: "🔥",
};

interface FanVoiceBubbleProps {
  bubble: ActiveFanVoiceBubble;
  onReact: (messageId: string) => void;
  onReport: (messageId: string) => void;
}

export function FanVoiceBubble({
  bubble,
  onReact,
  onReport,
}: FanVoiceBubbleProps) {
  const symbol = bubble.message.emotion_tag
    ? EMOTION_SYMBOL[bubble.message.emotion_tag]
    : null;
  const count = bubble.message.reaction_count;

  return (
    <div
      className="fan-voice-bubble"
      style={{ animationDuration: `${bubble.durationSec}s` }}
      title={bubble.message.session_alias}
    >
      {symbol ? (
        <span className="fan-voice-badge" aria-hidden="true">
          {symbol}
        </span>
      ) : null}
      <span>{bubble.message.message}</span>
      <span className="fan-voice-actions">
        <button
          type="button"
          className="fan-voice-action-btn"
          onClick={() => onReact(bubble.message.id)}
          title="좋아요"
        >
          ♥{count > 0 ? ` ${count}` : ""}
        </button>
        <button
          type="button"
          className="fan-voice-action-btn"
          onClick={() => onReport(bubble.message.id)}
          title="신고"
        >
          ⚑
        </button>
      </span>
    </div>
  );
}
