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
      className="relative pt-10 pb-10 overflow-hidden"
      style={{
        background:
          'radial-gradient(ellipse at 12% 18%, rgba(var(--lotte-blue-rgb), 0.24) 0%, transparent 36%), radial-gradient(ellipse at 86% 72%, rgba(var(--lotte-red-rgb), 0.12) 0%, transparent 34%), linear-gradient(135deg, rgba(var(--lotte-cream-rgb), 0.7) 0%, transparent 100%)',
      }}
    >
      <div
        className="absolute inset-x-0 top-0 h-[1px]"
        aria-hidden="true"
        style={{ background: 'linear-gradient(90deg, transparent, var(--blue), transparent)' }}
      />

      {/* Decorative season watermark */}
      <div
        className="pointer-events-none absolute select-none"
        aria-hidden="true"
        style={{
          top: '-16px',
          right: '-8px',
          fontSize: 'clamp(130px, 20vw, 210px)',
          fontFamily: 'var(--font-giants-inline), var(--font-giants), serif',
          color: 'transparent',
          WebkitTextStroke: '1px rgba(var(--lotte-navy-rgb), 0.18)',
          lineHeight: 1,
          letterSpacing: '-0.04em',
          userSelect: 'none',
        }}
      >
        2026
      </div>

      {/* Top row: date + live kicker badge + status */}
      <div className="flex items-center gap-3 mb-4 animate-fade-in flex-wrap">
        <p
          className="text-xs font-mono-code tracking-widest uppercase"
          style={{ color: 'var(--dim)' }}
        >
          {date}
        </p>
        {kicker ? (
          <div
            className="inline-flex items-center gap-2 rounded-full px-2.5 py-1"
            style={{
              background: 'rgba(var(--lotte-blue-rgb), 0.14)',
              border: '1px solid var(--blue-border)',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0 animate-live-dot"
              style={{ background: 'var(--red)' }}
            />
            <p
              className="text-xs font-mono-code tracking-widest uppercase"
              style={{ color: 'var(--text)' }}
            >
              {kicker}
            </p>
          </div>
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

      {/* Animated red rule */}
      <div
        className="h-[2px] w-10 mb-5 animate-expand-width"
        style={{ background: 'var(--gradient-navy-band)', animationDelay: '150ms' }}
      />

      {/* Subcopy + metaStat */}
      <div
        className="flex flex-col items-start gap-4 animate-fade-up sm:flex-row sm:items-end sm:justify-between sm:gap-6"
        style={{ animationDelay: '80ms' }}
      >
        <p
          className="text-sm leading-relaxed max-w-lg"
          style={{ color: 'var(--muted)' }}
        >
          {subcopy}
        </p>
        {metaStat ? (
          <div className="text-left sm:shrink-0 sm:text-right">
            <p
              className="text-3xl font-bold font-mono-code leading-none"
              style={{ color: 'var(--text)' }}
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
