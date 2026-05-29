import { LabelBadge, StanceBadge } from './Badges'
import { LABEL_META } from '@/lib/label-config'
import type { Article } from '@/lib/types'
import { formatRelativeTime } from '@/lib/time'

type ArticleCardVariant = 'default' | 'compact'

interface ArticleCardProps {
  article: Article
  variant?: ArticleCardVariant
  showKeyPlayers?: boolean
}

export function ArticleCard({ article, variant = 'default', showKeyPlayers = true }: ArticleCardProps) {
  const labelDot = article.primary_label ? LABEL_META[article.primary_label].dot : 'var(--dim)'
  const isCompact = variant === 'compact'

  return (
    <article className="group relative rounded-2xl overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_6px_20px_rgba(96,62,27,0.09)]" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
      <div className="absolute top-0 left-0 h-full w-[3px] group-hover:w-[4px] transition-all duration-200" style={{ background: labelDot }} />
      <div className={isCompact ? 'pl-4 pr-4 pt-3 pb-3' : 'pl-4 pr-4 pt-3.5 pb-3.5'}>
        <div className="flex items-center gap-1.5 mb-2 flex-wrap">
          {article.primary_label ? <LabelBadge label={article.primary_label} /> : null}
          {article.lotte_stance ? <StanceBadge stance={article.lotte_stance} /> : null}
          <span className="text-[10px] font-mono-code ml-auto whitespace-nowrap shrink-0" style={{ color: 'var(--dim)' }}>
            {article.source_name} · {formatRelativeTime(article.published_at)}
          </span>
        </div>

        <h3 className={`font-semibold leading-snug transition-colors ${isCompact ? 'text-sm mb-1' : 'text-sm mb-1.5'}`} style={{ color: 'var(--text)' }}>
          {article.title}
        </h3>

        {article.event_summary ? (
          <p className={`text-xs leading-relaxed line-clamp-2 ${isCompact ? 'mb-2' : 'mb-2.5'}`} style={{ color: 'var(--muted)' }}>
            {article.event_summary}
          </p>
        ) : null}

        {showKeyPlayers && article.key_players && article.key_players.length > 0 ? (
          <div className="flex flex-wrap gap-1 mb-2.5">
            {article.key_players.map((name) => (
              <span
                key={name}
                className="text-[10px] px-1.5 py-0 rounded"
                style={{
                  background: 'var(--surface-2)',
                  color: 'var(--dim)',
                  border: '1px solid var(--border)',
                  lineHeight: '18px',
                }}
              >
                {name}
              </span>
            ))}
          </div>
        ) : null}

        <div className="flex items-center justify-end">
          <a
            href={article.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] font-mono-code uppercase tracking-widest transition-colors hover:text-lotte-red"
            style={{ color: 'var(--dim)' }}
          >
            원문 보기
          </a>
        </div>
      </div>
    </article>
  )
}
