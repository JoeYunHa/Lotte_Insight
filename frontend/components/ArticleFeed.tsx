'use client'

// Client component: manages label filter state.
// Receives all articles from the server component (no client-side fetch needed).

import { useState } from 'react'
import { ArticleCard } from './ArticleCard'
import { LABEL_META, ALL_LABELS } from '@/lib/label-config'
import { computeLabelCounts } from '@/lib/selectors'
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
        className="sticky top-14 z-40 -mx-4 px-4 pt-2"
        style={{
          background: 'rgba(6, 19, 37, 0.96)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        {/* FILTER DESK label */}
        <p
          className="text-[9px] font-mono-code uppercase tracking-widest mb-1"
          style={{ color: 'var(--dim)' }}
        >
          FILTER DESK
        </p>

        {/* Tabs with right fade mask */}
        <div className="relative">
          <div
            className="absolute right-0 top-0 bottom-0 w-8 pointer-events-none z-10"
            style={{
              background: 'linear-gradient(to right, transparent, rgba(6,19,37,0.96))',
            }}
          />
          <div className="flex gap-0 overflow-x-auto">
            {tabs.map(tab => {
              const isActive = activeFilter === tab.key
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveFilter(tab.key)}
                  className="flex-none flex items-center gap-1.5 px-3 py-2.5 text-xs transition-all whitespace-nowrap"
                  style={{
                    color: isActive ? 'var(--text)' : 'var(--dim)',
                    fontWeight: isActive ? 700 : 500,
                    borderBottom: isActive ? '2px solid var(--red)' : '2px solid transparent',
                    marginBottom: '-1px',
                  }}
                >
                  {tab.name}
                  {tab.count > 0 && (
                    <span
                      className="font-mono-code"
                      style={{
                        color: isActive ? 'var(--gold)' : 'var(--dim)',
                        fontSize: '10px',
                      }}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
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
