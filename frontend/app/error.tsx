'use client'

interface Props {
  error: Error & { digest?: string }
  reset: () => void
}

export default function Error({ error, reset }: Props) {
  return (
    <div
      className="min-h-dvh flex flex-col items-center justify-center px-4 gap-4"
      style={{ background: 'var(--bg)' }}
    >
      <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
        오류가 발생했습니다
      </p>
      <p className="text-xs text-center max-w-xs" style={{ color: 'var(--dim)' }}>
        {error.message}
      </p>
      <button
        onClick={reset}
        className="text-xs px-4 py-2 rounded transition-colors"
        style={{
          background: 'var(--surface)',
          color: 'var(--muted)',
          border: '1px solid var(--border)',
        }}
      >
        다시 시도
      </button>
    </div>
  )
}
