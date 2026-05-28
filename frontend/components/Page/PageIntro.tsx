interface PageIntroProps {
  season?: string
  title: string
  subtitle?: string
}

export function PageIntro({ season = '2026 KBO Season', title, subtitle }: PageIntroProps) {
  return (
    <div className="pt-10 pb-6">
      <p className="text-xs font-medium mb-3 font-mono-code" style={{ color: 'var(--muted)' }}>
        {season}
      </p>
      <h1
        className={`font-serif-kr text-3xl font-black leading-tight ${subtitle ? 'mb-1' : 'mb-4'}`}
        style={{ color: 'var(--text)' }}
      >
        {title}
      </h1>
      {subtitle ? (
        <p className="text-sm mb-4" style={{ color: 'var(--dim)' }}>
          {subtitle}
        </p>
      ) : null}
      <div className="h-px w-full" style={{ background: 'var(--border)' }} />
    </div>
  )
}
