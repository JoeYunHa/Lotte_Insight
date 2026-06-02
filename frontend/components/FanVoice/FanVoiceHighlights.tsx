"use client";

import type { FanVoiceEmotion, FanVoiceMessage } from "@/lib/fan-voice/fan-voice-types";

const EMOTION_SYMBOL: Record<FanVoiceEmotion, string> = {
  CHEER: "📣",
  EXPECT: "⭐",
  FRUSTRATED: "😤",
  MOVED: "🥺",
  ANGRY: "🔥",
};

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

  const maxReactions = Math.max(...top.map((m) => m.reaction_count), 1);

  return (
    <div
      className="mb-2 rounded-xl overflow-hidden"
      style={{
        border: "1px solid var(--border)",
        background: "var(--gradient-surface)",
      }}
    >
      {/* Header */}
      <div
        className="px-3 py-1.5 flex items-center gap-2"
        style={{
          borderBottom: "1px solid var(--border)",
          background: "var(--surface-overlay)",
        }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0 animate-live-dot"
          style={{ background: "var(--gold)" }}
        />
        <p
          className="text-[10px] font-bold uppercase tracking-[0.18em]"
          style={{ color: "var(--dim)" }}
        >
          인기 팬보이스
        </p>
      </div>

      {/* Voice list */}
      <ul>
        {top.map((item, idx) => {
          const barPct = Math.round((item.reaction_count / maxReactions) * 100);
          const symbol = item.emotion_tag
            ? EMOTION_SYMBOL[item.emotion_tag]
            : "💬";
          return (
            <li
              key={item.id}
              className="flex items-center gap-2.5 px-3 py-2"
              style={{
                borderBottom:
                  idx < top.length - 1 ? "1px solid var(--border)" : undefined,
              }}
            >
              <span
                className="text-sm shrink-0 w-5 text-center select-none leading-none"
                aria-label={item.emotion_tag ?? ""}
              >
                {symbol}
              </span>
              <p
                className="text-xs flex-1 truncate"
                style={{ color: "var(--text)" }}
              >
                {item.message}
              </p>
              <div className="shrink-0 flex items-center gap-1.5">
                <div
                  className="rounded-full overflow-hidden"
                  style={{
                    width: 28,
                    height: 3,
                    background: "var(--surface-2)",
                  }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${barPct}%`,
                      background:
                        idx === 0 ? "var(--gold)" : "var(--border-strong)",
                    }}
                  />
                </div>
                <span
                  className="text-[10px] font-mono-code tabular-nums w-4 text-right"
                  style={{ color: idx === 0 ? "var(--gold)" : "var(--dim)" }}
                >
                  {item.reaction_count}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
