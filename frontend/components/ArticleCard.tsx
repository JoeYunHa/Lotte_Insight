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

export function ArticleCard({
  article,
  variant = 'default',
  showKeyPlayers = true,
}: ArticleCardProps) {
  const labelDot = article.primary_label ? LABEL_META[article.primary_label].dot : 'var(--dim)'
  const isCompact = variant === 'compact'

  return (
    <article
      className={`group relative rounded-lg overflow-hidden transition-all duration-200 ${
        isCompact ? '' : 'hover:-translate-y-px'
      }`}
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <div className="absolute top-0 left-0 w-[3px] h-full" style={{ background: labelDot }} />
      <div className={isCompact ? 'pl-4 pr-4 pt-3 pb-3' : 'pl-4 pr-4 pt-3.5 pb-3.5'}>
        <div className={isCompact ? 'flex items-center gap-2 mb-1.5' : 'flex items-center gap-2 mb-2'}>
          {article.primary_label ? <LabelBadge label={article.primary_label} /> : null}
          {article.lotte_stance ? <StanceBadge stance={article.lotte_stance} /> : null}
        </div>

        <h3
          className={`text-sm font-semibold leading-snug transition-colors ${
            isCompact ? 'mb-1' : 'mb-1.5 group-hover:text-cream-100'
          }`}
          style={{ color: 'var(--text)' }}
        >
          {article.title}
        </h3>

        {article.event_summary ? (
          <p
            className={isCompact ? 'text-xs leading-relaxed mb-2' : 'text-xs leading-relaxed mb-2.5'}
            style={{ color: 'var(--muted)' }}
          >
            {article.event_summary}
          </p>
        ) : null}

        {showKeyPlayers && article.key_players && article.key_players.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 mb-2.5">
            {article.key_players.map(name => (
              <span
                key={name}
                className="text-xs px-1.5 py-0.5 rounded"
                style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
              >
                {name}
              </span>
            ))}
          </div>
        ) : null}

        <div className="flex items-center justify-between">
          <span className="text-xs" style={{ color: 'var(--dim)' }}>
            {article.source_name} · {formatRelativeTime(article.published_at)}
          </span>
          <a
            href={article.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`text-xs transition-colors hover:text-lotte-red ${isCompact ? '' : 'font-medium'}`}
            style={{ color: 'var(--muted)' }}
          >
            원문 보기
          </a>
        </div>
      </div>
    </article>
  )
}
