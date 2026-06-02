import { LabelBadge, StanceBadge } from './Badges'
import type { Article } from '@/lib/types'
import { formatRelativeTime } from '@/lib/time'

interface FeaturedArticleCardProps {
  article: Article | null
  eyebrow?: string
}

export function FeaturedArticleCard({
  article,
  eyebrow = '주요 기사',
}: FeaturedArticleCardProps) {
  if (!article) {
    return (
      <section
        className="rounded-[28px] p-6 md:p-7"
        style={{
          background: 'var(--gradient-surface)',
          border: '1px solid var(--border)',
        }}
      >
        <p className="text-xs font-mono-code uppercase tracking-[0.24em]" style={{ color: 'var(--gold)' }}>
          {eyebrow}
        </p>
        <h2 className="mt-4 text-2xl font-serif-kr font-bold" style={{ color: 'var(--text)' }}>
          아직 주요 기사가 없습니다
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-7" style={{ color: 'var(--muted)' }}>
          대시보드가 준비되었습니다. 기사 수집이 완료되면 주요 기사와 요약이 여기에 표시됩니다.
        </p>
      </section>
    )
  }

  return (
    <section
      className="rounded-[28px] p-6 md:p-7"
      style={{
        background: 'var(--gradient-surface-accent)',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow-hero)',
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
          className="group/link inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-all"
          style={{
            background: 'var(--surface-glass-muted)',
            color: 'var(--text)',
            border: '1px solid var(--red-border)',
          }}
        >
          원문 기사 보기
          <span
            className="inline-block transition-transform group-hover/link:translate-x-0.5"
            aria-hidden="true"
          >
            →
          </span>
        </a>
      </div>
    </section>
  )
}
