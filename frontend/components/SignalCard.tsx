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
  const accentColor =
    accent === 'red' ? 'var(--red)' :
    accent === 'navy' ? 'var(--text)' :
    'var(--blue)'
  const valueColor = accent === 'blue' ? 'var(--text)' : accentColor
  const borderColor =
    accent === 'red' ? 'var(--red-border)' :
    accent === 'navy' ? 'var(--navy-border)' :
    'var(--blue-border)'
  const panelBackground =
    accent === 'red'
      ? 'linear-gradient(180deg, rgba(var(--lotte-red-rgb), 0.14) 0%, rgba(var(--lotte-cream-rgb), 0.94) 28%, rgba(var(--lotte-white-rgb), 0.86) 100%)'
      : accent === 'navy'
        ? 'linear-gradient(180deg, rgba(var(--lotte-navy-rgb), 0.92) 0%, rgba(var(--lotte-navy-rgb), 0.86) 22%, rgba(var(--lotte-cream-rgb), 0.96) 22%, rgba(var(--lotte-white-rgb), 0.88) 100%)'
        : 'linear-gradient(180deg, rgba(var(--lotte-blue-rgb), 0.2) 0%, rgba(var(--lotte-cream-rgb), 0.94) 28%, rgba(var(--lotte-white-rgb), 0.88) 100%)'
  const mutedColor = accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.78)' : 'var(--muted)'

  return (
    <div
      className="card-surface rounded-lg p-4 animate-fade-up"
      style={{
        border: `1px solid ${borderColor}`,
        borderTop: `3px solid ${accentColor}`,
        background: panelBackground,
        animationDelay: `${delay}ms`,
      }}
    >
      {eyebrow ? (
        <p
          className="text-[9px] font-mono-code uppercase tracking-widest mb-1"
          style={{ color: accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.72)' : accentColor }}
        >
          {eyebrow}
        </p>
      ) : null}
      <p
        className="text-[10px] font-mono-code uppercase tracking-widest mb-2"
        style={{ color: accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.72)' : 'var(--dim)' }}
      >
        {title}
      </p>
      {value ? (
        <p
          className="text-3xl font-bold font-mono-code leading-none mb-1"
          style={{ color: valueColor }}
        >
          {value}
        </p>
      ) : null}
      {detail ? (
        <p className="text-xs mt-1.5" style={{ color: mutedColor }}>
          {detail}
        </p>
      ) : null}
      {children}
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
      {/* Bar */}
      <div className="flex rounded-full overflow-hidden h-1.5 gap-px">
        {pos > 0 && <div style={{ width: `${pos}%`, background: 'var(--win)' }} />}
        {neu > 0 && <div style={{ width: `${neu}%`, background: 'var(--neutral)' }} />}
        {neg > 0 && <div style={{ width: `${neg}%`, background: 'var(--loss)' }} />}
      </div>

      {/* Legend */}
      <div className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-1">
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--win)' }}>긍정 {pos}%</span>
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--neutral)' }}>중립 {neu}%</span>
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--loss)' }}>부정 {neg}%</span>
      </div>

      {/* Coverage sub-line */}
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--dim)' }}>
          {total}건 중 {analyzed}건 분석됨
        </span>
        {isPartial ? (
          <span
            className="chip-surface text-[9px] font-mono-code px-1 rounded"
            style={{
              color: 'var(--blue)',
              lineHeight: '16px',
            }}
          >
            일부
          </span>
        ) : null}
      </div>
    </div>
  )
}
