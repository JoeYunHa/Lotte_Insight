import type { ReactNode } from 'react'

type SignalAccent = 'red' | 'gold' | 'neutral'

interface SignalCardProps {
  title: string
  value: string
  detail?: string
  delay?: number
  children?: ReactNode
  accent?: SignalAccent
  eyebrow?: string
}

export function SignalCard({ title, value, detail, delay = 0, children, accent = 'neutral', eyebrow }: SignalCardProps) {
  const accentColor = accent === 'red' ? 'var(--red)' : accent === 'gold' ? 'var(--gold)' : 'var(--blue)'
  const valueColor = accent === 'red' ? 'var(--red)' : accent === 'gold' ? 'var(--gold)' : 'var(--text)'
  const panelBackground =
    accent === 'red'
      ? 'linear-gradient(180deg, rgba(var(--lotte-white-rgb), 0.98) 0%, rgba(var(--lotte-red-rgb), 0.05) 100%)'
      : accent === 'gold'
        ? 'linear-gradient(180deg, rgba(var(--lotte-white-rgb), 0.98) 0%, rgba(var(--lotte-gold-rgb), 0.07) 100%)'
        : 'linear-gradient(180deg, rgba(var(--lotte-white-rgb), 0.98) 0%, rgba(var(--lotte-blue-rgb), 0.1) 100%)'

  return (
    <div
      className="card-surface rounded-lg p-4 animate-fade-up"
      style={{
        borderTop: `2px solid ${accentColor}`,
        background: panelBackground,
        animationDelay: `${delay}ms`,
      }}
    >
      {eyebrow ? (
        <p
          className="text-[9px] font-mono-code uppercase tracking-widest mb-1"
          style={{ color: accentColor ?? 'var(--dim)' }}
        >
          {eyebrow}
        </p>
      ) : null}
      <p
        className="text-[10px] font-mono-code uppercase tracking-widest mb-2"
        style={{ color: 'var(--dim)' }}
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
        <p className="text-xs mt-1.5" style={{ color: 'var(--muted)' }}>
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
      <div className="flex gap-2.5 mt-1.5">
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--win)' }}>긍정 {pos}%</span>
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--neutral)' }}>중립 {neu}%</span>
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--loss)' }}>부정 {neg}%</span>
      </div>

      {/* Coverage sub-line */}
      <div className="flex items-center gap-1.5 mt-1">
        <span className="text-[10px] font-mono-code" style={{ color: 'var(--dim)' }}>
          {total}건 중 {analyzed}건 분석됨
        </span>
        {isPartial ? (
          <span
            className="chip-surface text-[9px] font-mono-code px-1 rounded"
            style={{
              color: 'var(--gold)',
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
