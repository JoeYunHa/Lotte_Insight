"use client";

import type { ActiveFanVoiceBubble } from "@/lib/fan-voice/fan-voice-lane-scheduler";

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
  return (
    <div
      className="fan-voice-bubble"
      style={{
        animationDuration: `${bubble.durationSec}s`,
      }}
      title={bubble.message.session_alias}
    >
      {bubble.message.emotion_tag ? (
        <span className="fan-voice-badge">{bubble.message.emotion_tag}</span>
      ) : null}
      <span>{bubble.message.message}</span>
      <span className="fan-voice-actions">
        <button
          type="button"
          className="fan-voice-action-btn"
          onClick={() => onReact(bubble.message.id)}
          title="React"
        >
          +1
        </button>
        <button
          type="button"
          className="fan-voice-action-btn"
          onClick={() => onReport(bubble.message.id)}
          title="Report"
        >
          !
        </button>
      </span>
    </div>
  );
}
