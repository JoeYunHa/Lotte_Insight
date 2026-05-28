"use client";

import { FanVoiceBubble } from "./FanVoiceBubble";
import type { ActiveFanVoiceBubble } from "@/lib/fan-voice/fan-voice-lane-scheduler";

interface FanVoiceLaneProps {
  laneIndex: number;
  bubbles: ActiveFanVoiceBubble[];
  onReact: (messageId: string) => void;
  onReport: (messageId: string) => void;
}

export function FanVoiceLane({
  laneIndex,
  bubbles,
  onReact,
  onReport,
}: FanVoiceLaneProps) {
  return (
    <div className="fan-voice-lane" data-lane={laneIndex}>
      {bubbles.map((bubble) => (
        <FanVoiceBubble
          key={bubble.localId}
          bubble={bubble}
          onReact={onReact}
          onReport={onReport}
        />
      ))}
    </div>
  );
}
