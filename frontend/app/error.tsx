'use client'

interface Props {
  error: Error & { digest?: string }
  reset: () => void
}

export default function Error({ error, reset }: Props) {
  return (
    <div className="min-h-dvh flex flex-col items-center justify-center px-4 gap-4" style={{ background: 'var(--bg)' }}>
      <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
        Something went wrong
      </p>
      <p className="text-xs text-center max-w-xs" style={{ color: 'var(--dim)' }}>
        {error.message}
      </p>
      <button
        onClick={reset}
        className="card-surface text-xs px-4 py-2 rounded transition-colors"
        style={{
          color: 'var(--muted)',
        }}
      >
        Retry
      </button>
    </div>
  )
}
