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
        className="overflow-hidden rounded-[28px]"
        style={{
          background: 'var(--gradient-surface)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div
          className="px-6 py-5 md:px-7"
          style={{ background: 'linear-gradient(135deg, rgba(var(--lotte-blue-rgb), 0.22) 0%, rgba(var(--lotte-navy-rgb), 0.82) 100%)' }}
        >
          <p className="inline-flex rounded-full bg-[rgba(255,255,255,0.12)] px-2.5 py-1 text-xs font-mono-code uppercase tracking-[0.24em]" style={{ color: 'rgba(var(--lotte-cream-rgb), 0.94)' }}>
            {eyebrow}
          </p>
        </div>
        <div className="px-6 py-6 md:px-7">
          <h2 className="text-2xl font-serif-kr font-bold" style={{ color: 'var(--text)' }}>
            아직 주요 기사가 없습니다
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7" style={{ color: 'var(--muted)' }}>
            대시보드가 준비되었습니다. 기사 수집이 완료되면 주요 기사와 요약이 여기에 표시됩니다.
          </p>
        </div>
      </section>
    )
  }

  return (
    <section
      className="overflow-hidden rounded-[28px]"
      style={{
        background: 'var(--gradient-surface-accent)',
        border: '1px solid var(--blue-border)',
        boxShadow: 'var(--shadow-hero)',
      }}
    >
      <div
        className="px-6 py-5 md:px-7"
        style={{
          background: 'linear-gradient(135deg, rgba(var(--lotte-navy-rgb), 0.96) 0%, rgba(var(--lotte-blue-rgb), 0.82) 100%)',
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="rounded-full bg-[rgba(255,255,255,0.12)] px-2.5 py-1 text-xs font-mono-code uppercase tracking-[0.24em]" style={{ color: 'rgba(var(--lotte-cream-rgb), 0.94)' }}>
            {eyebrow}
          </p>
          {article.primary_label ? <LabelBadge label={article.primary_label} /> : null}
          {article.lotte_stance ? <StanceBadge stance={article.lotte_stance} /> : null}
        </div>

        <h2 className="mt-4 text-[1.8rem] leading-tight font-serif-kr font-black md:text-[2.4rem]" style={{ color: 'var(--text-on-accent)' }}>
          {article.title}
        </h2>
      </div>

      <div className="px-6 py-6 md:px-7">
        {article.event_summary ? (
          <p className="max-w-3xl text-base leading-8" style={{ color: 'var(--muted)' }}>
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
              background: 'var(--surface-navy)',
              color: 'var(--text-on-accent)',
              border: '1px solid rgba(var(--lotte-blue-rgb), 0.3)',
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
      </div>
    </section>
  )
}
