'use client'

// Client component: manages label filter state.
// Receives all articles from the server component (no client-side fetch needed).

import { useState } from 'react'
import { ArticleCard } from './ArticleCard'
import { LABEL_META, ALL_LABELS } from '@/lib/label-config'
import { computeLabelCounts } from '@/lib/api'
import type { Article, LabelKey } from '@/lib/types'

type FilterKey = 'ALL' | LabelKey

interface Props {
  articles: Article[]
}

export function ArticleFeed({ articles }: Props) {
  const [activeFilter, setActiveFilter] = useState<FilterKey>('ALL')
  const labelCounts = computeLabelCounts(articles)

  const filtered =
    activeFilter === 'ALL'
      ? articles
      : articles.filter(a => a.primary_label === activeFilter)

  const tabs: { key: FilterKey; name: string; count: number }[] = [
    { key: 'ALL', name: '전체', count: articles.length },
    ...ALL_LABELS
      .filter(l => labelCounts[l] > 0)
      .map(l => ({ key: l as FilterKey, name: LABEL_META[l].name, count: labelCounts[l] })),
  ]

  return (
    <div>
      {/* ── Filter tabs (sticky under header) ── */}
      <div
        className="sticky top-14 z-40 -mx-4 px-4 pb-3 pt-2"
        style={{ background: 'var(--bg)' }}
      >
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {tabs.map(tab => {
            const isActive = activeFilter === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => setActiveFilter(tab.key)}
                className="flex-none flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap"
                style={{
                  background: isActive ? 'var(--red)' : 'var(--surface)',
                  color: isActive ? '#fff' : 'var(--muted)',
                  border: `1px solid ${isActive ? 'var(--red)' : 'var(--border)'}`,
                }}
              >
                {tab.name}
                {tab.count > 0 && (
                  <span
                    className="font-mono-code"
                    style={{ opacity: isActive ? 0.85 : 0.6, fontSize: '10px' }}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        <div className="h-px w-full mt-2" style={{ background: 'var(--border)' }} />
      </div>

      {/* ── Article list ── */}
      <div className="space-y-3 pt-3">
        {filtered.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm" style={{ color: 'var(--dim)' }}>
              해당 분류의 기사가 없습니다
            </p>
          </div>
        ) : (
          filtered.map(article => (
            <ArticleCard key={article.id} article={article} />
          ))
        )}
      </div>
    </div>
  )
}
