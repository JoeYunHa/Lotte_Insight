'use client'

interface FanVoiceToggleProps {
  open: boolean
  onToggle: (next: boolean) => void
}

export function FanVoiceToggle({ open, onToggle }: FanVoiceToggleProps) {
  return (
    <button
      type="button"
      onClick={() => onToggle(!open)}
      className="fixed right-5 bottom-5 z-50 inline-flex h-12 w-12 items-center justify-center rounded-full border text-xl transition hover:-translate-y-px"
      style={{
        borderColor: 'rgba(var(--lotte-navy-rgb), 0.18)',
        background: '#ffffff',
        color: 'var(--text)',
        boxShadow: '0 14px 30px rgba(var(--lotte-navy-rgb), 0.18)',
      }}
      aria-label={open ? '팬 보이스 채팅 닫기' : '팬 보이스 채팅 열기'}
      aria-pressed={open}
    >
      <span aria-hidden="true">{open ? '✕' : '💬'}</span>
    </button>
  )
}
