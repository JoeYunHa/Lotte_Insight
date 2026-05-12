import { LabelBadge } from './Badges'
import { LABEL_META } from '@/lib/label-config'
import type { LabelKey } from '@/lib/types'

interface LeadIssueCardProps {
  label: LabelKey
  summary: string
  articleCount: number
  keyPlayers?: string[]
  title?: string
  note?: string
}

export function LeadIssueCard({ label, summary, articleCount, keyPlayers, title, note }: LeadIssueCardProps) {
  const dot = LABEL_META[label].dot

  return (
    <div
      className="rounded-lg overflow-hidden animate-fade-up"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border-strong)',
        borderLeft: `4px solid ${dot}`,
        animationDelay: '180ms',
      }}
    >
      {/* Header bar */}
      <div
        className="px-5 py-3 flex items-center gap-2"
        style={{
          background: 'rgba(255,255,255,0.025)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span
          className="text-[10px] font-mono-code uppercase tracking-widest font-bold shrink-0"
          style={{ color: 'var(--dim)' }}
        >
          LEAD ISSUE
        </span>
        <span className="text-[10px]" style={{ color: 'var(--border-strong)' }}>·</span>
        <LabelBadge label={label} />
        <span
          className="ml-auto text-sm font-bold font-mono-code shrink-0"
          style={{ color: 'var(--gold)' }}
        >
          {articleCount}건
        </span>
      </div>

      {/* Body */}
      <div className="p-5">
        {title ? (
          <h3
            className="text-base font-bold leading-snug mb-2"
            style={{ color: 'var(--text)' }}
          >
            {title}
          </h3>
        ) : null}

        <p
          className="text-sm leading-relaxed mb-4"
          style={{ color: 'var(--muted)' }}
        >
          {summary}
        </p>

        {/* Key players */}
        {keyPlayers && keyPlayers.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {keyPlayers.slice(0, 5).map(name => (
              <span
                key={name}
                className="text-xs px-2 py-0.5 rounded"
                style={{
                  background: 'var(--surface-2)',
                  color: 'var(--muted)',
                  border: '1px solid var(--border)',
                }}
              >
                {name}
              </span>
            ))}
          </div>
        ) : null}

        {note ? (
          <p className="text-xs italic" style={{ color: 'var(--dim)' }}>
            {note}
          </p>
        ) : null}
      </div>
    </div>
  )
}
