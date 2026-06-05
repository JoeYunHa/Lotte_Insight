"use client";

import { useState } from "react";

import { postFanVoiceMessage } from "@/lib/fan-voice/fan-voice-api";
import type {
  FanVoiceContextType,
  FanVoiceEmotion,
} from "@/lib/fan-voice/fan-voice-types";

interface FanVoiceComposerProps {
  contextType: FanVoiceContextType;
  contextId: string;
  disabled?: boolean;
  onSubmitted?: () => void;
}

type EmotionOption = { value: FanVoiceEmotion | ""; label: string };

const EMOTIONS: EmotionOption[] = [
  { value: "", label: "감정 없음" },
  { value: "CHEER", label: "응원 📣" },
  { value: "EXPECT", label: "기대 ⭐" },
  { value: "FRUSTRATED", label: "답답 😤" },
  { value: "MOVED", label: "감동 🥺" },
  { value: "ANGRY", label: "화남 🔥" },
];

export function FanVoiceComposer({
  contextType,
  contextId,
  disabled,
  onSubmitted,
}: FanVoiceComposerProps) {
  const [message, setMessage] = useState("");
  const [emotion, setEmotion] = useState<FanVoiceEmotion | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    !disabled &&
    !submitting &&
    message.trim().length > 0 &&
    message.trim().length <= 60;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await postFanVoiceMessage({
        context_type: contextType,
        context_id: contextId,
        message: message.trim(),
        emotion_tag: emotion || null,
      });
      setMessage("");
      setEmotion("");
      onSubmitted?.();
    } catch (submitError) {
      console.error("[fan-voice] post message failed", submitError);
      setError("메시지 전송에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-2xl border p-2"
      style={{
        borderColor: "rgba(var(--lotte-navy-rgb), 0.16)",
        background: "#ffffff",
        boxShadow: "0 10px 24px rgba(var(--lotte-navy-rgb), 0.1)",
      }}
    >
      <select
        className="rounded-md border px-2 py-1 text-xs"
        style={{
          borderColor: "rgba(var(--lotte-navy-rgb), 0.14)",
          color: "var(--text)",
          background: "#ffffff",
        }}
        value={emotion}
        onChange={(e) => setEmotion(e.target.value as FanVoiceEmotion | "")}
        disabled={disabled || submitting}
      >
        {EMOTIONS.map((option) => (
          <option key={option.label} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={message}
        maxLength={60}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="팬 의견을 남겨주세요..."
        className="min-w-[180px] flex-1 rounded-md border px-3 py-1.5 text-sm"
        style={{
          borderColor: "rgba(var(--lotte-navy-rgb), 0.14)",
          color: "var(--text)",
          background: "#ffffff",
        }}
        disabled={disabled || submitting}
      />
      <button
        type="button"
        onClick={submit}
        disabled={!canSubmit}
        className="rounded-md px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50"
        style={{
          background: "var(--red)",
          color: "var(--lotte-white)",
        }}
      >
        보내기
      </button>
      {error ? (
        <p className="basis-full text-xs" style={{ color: "var(--loss)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
