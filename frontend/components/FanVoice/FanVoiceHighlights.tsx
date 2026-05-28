"use client";

import type { FanVoiceMessage } from "@/lib/fan-voice/fan-voice-types";

interface FanVoiceHighlightsProps {
  messages: FanVoiceMessage[];
}

export function FanVoiceHighlights({ messages }: FanVoiceHighlightsProps) {
  if (!messages.length) return null;
  const top = [...messages]
    .sort(
      (a, b) =>
        b.reaction_count - a.reaction_count ||
        b.created_at.localeCompare(a.created_at),
    )
    .slice(0, 3);

  return (
    <div
      className="mb-2 rounded-xl border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        background: "rgba(255,255,255,0.78)",
      }}
    >
      <p
        className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em]"
        style={{ color: "var(--dim)" }}
      >
        Highlights
      </p>
      <ul className="space-y-1">
        {top.map((item) => (
          <li
            key={item.id}
            className="text-xs"
            style={{ color: "var(--muted)" }}
          >
            {item.message} ({item.reaction_count})
          </li>
        ))}
      </ul>
    </div>
  );
}
