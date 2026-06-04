'use client'

import { useState } from 'react'
import { ArticleCard } from './ArticleCard'
import { ALL_LABELS, LABEL_META } from '@/lib/label-config'
import { computeLabelCounts } from '@/lib/selectors'
import type { Article, LabelKey } from '@/lib/types'

type FilterKey = 'ALL' | LabelKey

interface Props {
  articles: Article[]
}

export function ArticleFeed({ articles }: Props) {
  const [activeFilter, setActiveFilter] = useState<FilterKey>('ALL')
  const labelCounts = computeLabelCounts(articles)

  const filtered = activeFilter === 'ALL' ? articles : articles.filter((article) => article.primary_label === activeFilter)
  const tabs: { key: FilterKey; name: string; count: number }[] = [
    { key: 'ALL', name: '전체', count: articles.length },
    ...ALL_LABELS.filter((label) => labelCounts[label] > 0).map((label) => ({ key: label as FilterKey, name: LABEL_META[label].name, count: labelCounts[label] })),
  ]

  return (
    <div>
      <div
        className="sticky top-14 z-40 -mx-4 px-4 pt-3 pb-1"
        style={{
          background: 'var(--surface-glass-strong)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <p className="text-[10px] font-mono-code uppercase tracking-[0.22em] mb-2" style={{ color: 'var(--muted)' }}>
          필터 보드
        </p>

        <div className="relative">
          <div className="absolute right-0 top-0 bottom-0 w-8 pointer-events-none z-10" style={{ background: 'linear-gradient(to right, transparent, var(--surface-glass))' }} />
          <div className="flex gap-2 overflow-x-auto pb-1">
            {tabs.map((tab) => {
              const isActive = activeFilter === tab.key
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveFilter(tab.key)}
                  className="flex-none flex items-center gap-2 rounded-full px-4 py-2 text-sm transition-all whitespace-nowrap"
                  style={{
                    color: isActive ? 'var(--text)' : 'var(--dim)',
                    fontWeight: isActive ? 700 : 500,
                    border: isActive ? '1px solid var(--red-border)' : '1px solid var(--border)',
                    background: isActive ? 'var(--red-soft)' : 'var(--surface-glass-muted)',
                  }}
                >
                  {tab.name}
                  {tab.count > 0 ? (
                    <span className="font-mono-code" style={{ color: isActive ? 'var(--red)' : 'var(--dim)', fontSize: '10px' }}>
                      {tab.count}
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="space-y-3 pt-3">
        {filtered.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm" style={{ color: 'var(--dim)' }}>
              이 카테고리에 기사가 없습니다.
            </p>
          </div>
        ) : (
          filtered.map((article) => <ArticleCard key={article.id} article={article} />)
        )}
      </div>
    </div>
  )
}
