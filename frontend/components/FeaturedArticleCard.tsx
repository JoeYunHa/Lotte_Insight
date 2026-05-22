import { LabelBadge, StanceBadge } from './Badges'
import type { Article } from '@/lib/types'
import { formatRelativeTime } from '@/lib/time'

interface FeaturedArticleCardProps {
  article: Article | null
  eyebrow?: string
}

export function FeaturedArticleCard({
  article,
  eyebrow = 'Featured Story',
}: FeaturedArticleCardProps) {
  if (!article) {
    return (
      <section
        className="rounded-[28px] p-6 md:p-7"
        style={{
          background:
            'linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(241,232,218,0.98) 100%)',
          border: '1px solid var(--border)',
        }}
      >
        <p className="text-xs font-mono-code uppercase tracking-[0.24em]" style={{ color: 'var(--gold)' }}>
          {eyebrow}
        </p>
        <h2 className="mt-4 text-2xl font-serif-kr font-bold" style={{ color: 'var(--text)' }}>
          No featured story yet
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-7" style={{ color: 'var(--muted)' }}>
          The dashboard is ready. As soon as article collection finishes, the lead article and summary will appear here.
        </p>
      </section>
    )
  }

  return (
    <section
      className="rounded-[28px] p-6 md:p-7 shadow-[0_20px_50px_rgba(96,62,27,0.10)]"
      style={{
        background:
          'radial-gradient(circle at top left, rgba(225,6,44,0.12), transparent 30%), linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(241,232,218,0.98) 100%)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-mono-code uppercase tracking-[0.24em]" style={{ color: 'var(--gold)' }}>
          {eyebrow}
        </p>
        {article.primary_label ? <LabelBadge label={article.primary_label} /> : null}
        {article.lotte_stance ? <StanceBadge stance={article.lotte_stance} /> : null}
      </div>

      <h2 className="mt-4 text-[1.8rem] leading-tight font-serif-kr font-black md:text-[2.4rem]" style={{ color: 'var(--text)' }}>
        {article.title}
      </h2>

      {article.event_summary ? (
        <p className="mt-4 max-w-3xl text-base leading-8" style={{ color: 'var(--muted)' }}>
          {article.event_summary}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm" style={{ color: 'var(--dim)' }}>
        <span>{article.source_name}</span>
        <span>{formatRelativeTime(article.published_at)}</span>
        {article.key_players && article.key_players.length > 0 ? (
          <span>{article.key_players.slice(0, 3).join(' / ')}</span>
        ) : null}
      </div>

      <div className="mt-6">
        <a
          href={article.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center rounded-full px-4 py-2 text-sm font-semibold transition-colors"
          style={{
            background: 'rgba(255,255,255,0.7)',
            color: 'var(--text)',
            border: '1px solid rgba(225,6,44,0.26)',
          }}
        >
          Open original article
        </a>
      </div>
    </section>
  )
}
