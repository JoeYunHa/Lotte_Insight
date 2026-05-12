import type { ReactNode } from 'react'

interface HomeHeroDeskProps {
  date: string
  headline: string
  subcopy: string
  kicker?: string
  metaStat?: { label: string; value: string }
  statusBadge?: ReactNode
}

export function HomeHeroDesk({ date, headline, subcopy, kicker, metaStat, statusBadge }: HomeHeroDeskProps) {
  return (
    <div
      className="pt-10 pb-10"
      style={{
        background: 'radial-gradient(ellipse at 15% 60%, rgba(225,6,44,0.06) 0%, transparent 55%)',
      }}
    >
      {/* Top: date + kicker + optional status badge */}
      <div className="flex items-center gap-3 mb-4 animate-fade-in">
        <p
          className="text-xs font-mono-code tracking-widest uppercase"
          style={{ color: 'var(--dim)' }}
        >
          {date}
        </p>
        {kicker ? (
          <>
            <span style={{ color: 'var(--border-strong)' }}>·</span>
            <p
              className="text-xs font-mono-code tracking-widest uppercase"
              style={{ color: 'var(--red)' }}
            >
              {kicker}
            </p>
          </>
        ) : null}
        {statusBadge ? <div className="ml-auto">{statusBadge}</div> : null}
      </div>

      {/* Headline */}
      <h1
        className="font-serif-kr text-3xl sm:text-4xl font-black leading-tight mb-4 animate-fade-up"
        style={{ color: 'var(--text)' }}
      >
        {headline}
      </h1>

      {/* Red rule */}
      <div className="h-[2px] w-10 mb-5" style={{ background: 'var(--red)' }} />

      {/* Subcopy + metaStat */}
      <div
        className="flex items-end justify-between gap-6 animate-fade-up"
        style={{ animationDelay: '80ms' }}
      >
        <p
          className="text-sm leading-relaxed max-w-lg"
          style={{ color: 'var(--muted)' }}
        >
          {subcopy}
        </p>
        {metaStat ? (
          <div className="shrink-0 text-right">
            <p
              className="text-3xl font-bold font-mono-code leading-none"
              style={{ color: 'var(--gold)' }}
            >
              {metaStat.value}
            </p>
            <p
              className="text-[10px] font-mono-code uppercase tracking-widest mt-1"
              style={{ color: 'var(--dim)' }}
            >
              {metaStat.label}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
