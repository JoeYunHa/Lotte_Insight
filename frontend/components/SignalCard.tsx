import type { ReactNode } from 'react'

type SignalAccent = 'red' | 'blue' | 'navy'

interface SignalCardProps {
  title: string
  value: string
  detail?: string
  delay?: number
  children?: ReactNode
  accent?: SignalAccent
  eyebrow?: string
}

export function SignalCard({ title, value, detail, delay = 0, children, accent = 'blue', eyebrow }: SignalCardProps) {
  const theme =
    accent === 'red'
      ? {
          shell: 'linear-gradient(180deg, rgba(var(--lotte-red-rgb), 0.16) 0%, rgba(var(--lotte-cream-rgb), 0.98) 100%)',
          block: 'linear-gradient(135deg, rgba(var(--lotte-red-rgb), 0.96) 0%, rgba(var(--lotte-red-rgb), 0.84) 100%)',
          chip: 'rgba(var(--lotte-white-rgb), 0.14)',
          border: 'var(--red-border)',
          eyebrow: 'var(--lotte-navy)',
          title: 'var(--lotte-navy)',
          value: 'var(--lotte-navy)',
          body: 'var(--text)',
          detail: 'var(--muted)',
        }
      : accent === 'navy'
        ? {
            shell: 'linear-gradient(180deg, rgba(var(--lotte-navy-rgb), 0.96) 0%, rgba(var(--lotte-cream-rgb), 0.98) 100%)',
            block: 'linear-gradient(135deg, rgba(var(--lotte-navy-rgb), 0.98) 0%, rgba(var(--lotte-blue-rgb), 0.88) 100%)',
            chip: 'rgba(var(--lotte-white-rgb), 0.12)',
            border: 'var(--navy-border)',
            eyebrow: 'var(--lotte-navy)',
            title: 'var(--lotte-navy)',
            value: 'var(--lotte-navy)',
            body: 'var(--text)',
            detail: 'var(--muted)',
          }
        : {
            shell: 'linear-gradient(180deg, rgba(var(--lotte-blue-rgb), 0.18) 0%, rgba(var(--lotte-cream-rgb), 0.98) 100%)',
            block: 'linear-gradient(135deg, rgba(var(--lotte-blue-rgb), 0.94) 0%, rgba(var(--lotte-navy-rgb), 0.86) 100%)',
            chip: 'rgba(var(--lotte-white-rgb), 0.12)',
            border: 'var(--blue-border)',
            eyebrow: 'var(--lotte-navy)',
            title: 'var(--lotte-navy)',
            value: 'var(--lotte-navy)',
            body: 'var(--text)',
            detail: 'var(--muted)',
          }

  return (
    <div
      className="overflow-hidden rounded-[22px] animate-fade-up"
      style={{
        border: `1px solid ${theme.border}`,
        background: theme.shell,
        boxShadow: 'var(--shadow-card)',
        animationDelay: `${delay}ms`,
      }}
    >
      <div
        className="px-5 py-4"
        style={{
          background: theme.block,
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            {eyebrow ? (
              <p
                className="inline-flex rounded-full px-2.5 py-1 text-[9px] font-mono-code uppercase tracking-widest"
                style={{ color: theme.eyebrow, background: theme.chip }}
              >
                {eyebrow}
              </p>
            ) : null}
            <p
              className="mt-3 text-[10px] font-mono-code uppercase tracking-[0.22em]"
              style={{ color: theme.title }}
            >
              {title}
            </p>
          </div>
          <p
            className="shrink-0 text-4xl font-bold font-mono-code leading-none"
            style={{ color: theme.value }}
          >
            {value}
          </p>
        </div>
      </div>

      <div className="px-5 py-4">
        {detail ? (
          <p className="text-xs leading-6" style={{ color: theme.detail }}>
            {detail}
          </p>
        ) : null}
        <div className="mt-3" style={{ color: theme.body }}>
          {children}
        </div>
      </div>
    </div>
  )
}

interface SentimentBarProps {
  positive: number
  neutral: number
  negative: number
  analyzed: number
  total: number
}

export function SentimentBar({ positive, neutral, negative, analyzed, total }: SentimentBarProps) {
  const pos = Math.round(positive * 100)
  const neu = Math.round(neutral * 100)
  const neg = Math.round(negative * 100)
  const isPartial = total > 0 && analyzed / total < 0.5 && analyzed > 0

  return (
    <div className="mt-2">
      <div className="overflow-hidden rounded-full" style={{ background: 'rgba(var(--lotte-navy-rgb), 0.08)' }}>
        <div className="flex h-2 gap-px">
          {pos > 0 && <div style={{ width: `${pos}%`, background: 'var(--win)' }} />}
          {neu > 0 && <div style={{ width: `${neu}%`, background: 'var(--neutral)' }} />}
          {neg > 0 && <div style={{ width: `${neg}%`, background: 'var(--loss)' }} />}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-2.5 gap-y-1">
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--win)' }}>긍정 {pos}%</span>
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--neutral)' }}>중립 {neu}%</span>
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--loss)' }}>부정 {neg}%</span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--dim)' }}>
          {total}건 중 {analyzed}건 분석됨
        </span>
        {isPartial ? (
          <span
            className="rounded-full px-2 py-0.5 text-[9px] font-mono-code"
            style={{
              color: 'var(--blue)',
              background: 'rgba(var(--lotte-blue-rgb), 0.12)',
            }}
          >
            일부
          </span>
        ) : null}
      </div>
    </div>
  )
}
