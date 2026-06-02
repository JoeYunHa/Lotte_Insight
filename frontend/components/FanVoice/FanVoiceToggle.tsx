'use client'

interface FanVoiceToggleProps {
  cleanMode: boolean
  onToggle: (next: boolean) => void
}

export function FanVoiceToggle({ cleanMode, onToggle }: FanVoiceToggleProps) {
  return (
    <button
      type="button"
      onClick={() => onToggle(!cleanMode)}
      className="rounded-full border px-3 py-1 text-xs font-medium transition"
      style={{
        borderColor: 'var(--border)',
        background: cleanMode ? 'var(--surface-2)' : 'var(--surface-glass-muted)',
        color: 'var(--muted)',
      }}
      aria-pressed={cleanMode}
    >
      {cleanMode ? '팬 보이스 끄기' : '팬 보이스 켜기'}
    </button>
  )
}
