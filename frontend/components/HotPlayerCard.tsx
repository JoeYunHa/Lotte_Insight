import Link from 'next/link'
import type { PlayerMention } from '@/lib/types'

interface HotPlayerCardProps {
  playerMention: PlayerMention
  rank: number
  delay?: number
  summary?: string
  highlight?: boolean
}

export function HotPlayerCard({ playerMention, rank, delay = 0, summary, highlight }: HotPlayerCardProps) {
  const { player, mention_count } = playerMention

  return (
    <Link
      href={`/players/${player.id}`}
      className="block rounded-lg p-4 transition-all duration-200 group animate-fade-up"
      style={{
        background: 'var(--surface)',
        border: highlight ? '1px solid var(--gold)' : '1px solid var(--border)',
        animationDelay: `${delay}ms`,
      }}
    >
      <div className="flex items-start gap-3">
        {/* Rank — small meta, not the main event */}
        <span
          className="text-[10px] font-mono-code font-bold mt-1 w-4 shrink-0"
          style={{ color: highlight ? 'var(--gold)' : 'var(--dim)' }}
        >
          {String(rank).padStart(2, '0')}
        </span>

        {/* Player info */}
        <div className="flex-1 min-w-0">
          <div
            className="font-bold text-base leading-tight transition-colors group-hover:text-lotte-red"
            style={{ color: 'var(--text)' }}
          >
            {player.name}
          </div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--dim)' }}>
            {player.position}
          </div>
          {summary ? (
            <p className="text-xs mt-1.5 leading-snug" style={{ color: 'var(--muted)' }}>
              {summary}
            </p>
          ) : null}
        </div>

        {/* Mention count — gold mono, prominent */}
        <div className="shrink-0 text-right">
          <p
            className="text-2xl font-bold font-mono-code leading-none"
            style={{ color: 'var(--gold)' }}
          >
            {mention_count}
          </p>
          <p
            className="text-[10px] font-mono-code uppercase tracking-widest mt-0.5"
            style={{ color: 'var(--dim)' }}
          >
            언급
          </p>
        </div>
      </div>
    </Link>
  )
}
