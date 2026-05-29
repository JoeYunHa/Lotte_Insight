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
  const accentColor = accent === 'red' ? 'var(--red)' : accent === 'gold' ? 'var(--gold)' : undefined
  const valueColor = accent === 'red' ? 'var(--red)' : accent === 'gold' ? 'var(--gold)' : 'var(--text)'
  const topBorder = accentColor ? `2px solid ${accentColor}` : '1px solid var(--border)'

  return (
    <div
      className="rounded-lg p-4 animate-fade-up"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderTop: topBorder,
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
          {analyzed} of {total} analyzed
        </span>
        {isPartial ? (
          <span
            className="text-[9px] font-mono-code px-1 rounded"
            style={{
              background: 'var(--surface-2)',
              color: 'var(--gold)',
              border: '1px solid var(--border)',
              lineHeight: '16px',
            }}
          >
            partial
          </span>
        ) : null}
      </div>
    </div>
  )
}
