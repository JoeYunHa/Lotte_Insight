import { getLabelMeta } from '@/lib/label-config'
import { formatRelativeTime } from '@/lib/time'
import type { TopicArticlePoint } from '@/lib/types'

interface TopicArticleListProps {
  points: TopicArticlePoint[]
}

export function TopicArticleList({ points }: TopicArticleListProps) {
  const withArticle = points.filter((p) => p.article)

  if (withArticle.length === 0) {
    return (
      <p className="text-xs py-4 text-center" style={{ color: 'var(--dim)' }}>
        이 클러스터에 기사가 없습니다.
      </p>
    )
  }

  return (
    <div className="space-y-1.5">
      {withArticle.map((p) => {
        const article = p.article!
        return (
          <div
            key={p.article_id}
            className="card-surface rounded-xl px-3 py-2.5"
          >
            <p className="text-xs font-medium leading-snug mb-1.5" style={{ color: 'var(--text)' }}>
              {article.title}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-mono-code" style={{ color: 'var(--muted)' }}>
                {article.source_name}
              </span>
              <span className="text-[10px] font-mono-code" style={{ color: 'var(--dim)' }}>
                {formatRelativeTime(article.published_at)}
              </span>
              {(() => { const meta = getLabelMeta(article.primary_label); return meta ? (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${meta.badge}`}>
                  {meta.name}
                </span>
              ) : null })()}
            </div>
          </div>
        )
      })}
    </div>
  )
}
