"use client";

import { getBubbleColor } from "@/lib/fan-voice/fan-voice-colors";
import type { ActiveFanVoiceBubble } from "@/lib/fan-voice/fan-voice-lane-scheduler";
import { FanVoiceBubble } from "./FanVoiceBubble";

interface FanVoiceLaneProps {
  bubbles: ActiveFanVoiceBubble[];
  onReact: (messageId: string) => void;
  onReport: (messageId: string) => void;
}

export function FanVoiceLane({
  bubbles,
  onReact,
  onReport,
}: FanVoiceLaneProps) {
  return (
    <div className="fan-voice-lane">
      {bubbles.map((bubble) => (
        <FanVoiceBubble
          key={bubble.localId}
          bubble={bubble}
          color={getBubbleColor(bubble.message.session_alias)}
          onReact={onReact}
          onReport={onReport}
        />
      ))}
    </div>
  );
}
