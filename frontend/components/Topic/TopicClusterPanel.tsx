'use client'

import { findCluster, getClusterPoints } from '@/lib/topic-map-utils'
import { TopicArticleList } from './TopicArticleList'
import { TopicClusterCard } from './TopicClusterCard'
import type { TopicArticlePoint, TopicCluster } from '@/lib/types'

interface TopicClusterPanelProps {
  clusters: TopicCluster[]
  points: TopicArticlePoint[]
  clusterColorMap: Record<string, string>
  selectedClusterId: string | null
  onSelectCluster: (id: string | null) => void
}

export function TopicClusterPanel({
  clusters,
  points,
  clusterColorMap,
  selectedClusterId,
  onSelectCluster,
}: TopicClusterPanelProps) {
  const selectedCluster = findCluster(clusters, selectedClusterId)
  const clusterPoints = selectedClusterId ? getClusterPoints(points, selectedClusterId) : []

  if (clusters.length === 0) {
    return (
      <div className="card-surface rounded-[24px] p-5">
        <p className="text-xs text-center py-8" style={{ color: 'var(--dim)' }}>
          이 날짜의 클러스터가 없습니다.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Selected cluster detail */}
      {selectedCluster ? (
        <div
          className="rounded-[24px] p-5"
          style={{
            background: 'linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(241,232,218,0.9) 100%)',
            border: `1.5px solid ${clusterColorMap[selectedCluster.id] ?? 'var(--border)'}`,
            boxShadow: `0 8px 32px ${clusterColorMap[selectedCluster.id] ?? 'transparent'}1a`,
          }}
        >
          <p
            className="text-[10px] font-mono-code uppercase tracking-[0.18em] mb-3"
            style={{ color: clusterColorMap[selectedCluster.id] ?? 'var(--gold)' }}
          >
            선택된 클러스터
          </p>
          <p className="font-serif-kr font-bold text-lg leading-snug mb-1.5" style={{ color: 'var(--text)' }}>
            {selectedCluster.title}
          </p>
          <p className="text-xs leading-5 mb-3" style={{ color: 'var(--muted)' }}>
            {selectedCluster.summary}
          </p>
          {selectedCluster.key_players.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 mb-4">
              {selectedCluster.key_players.map((name) => (
                <span
                  key={name}
                  className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                  style={{ background: 'rgba(255,255,255,0.7)', color: 'var(--text)', border: '1px solid var(--border)' }}
                >
                  {name}
                </span>
              ))}
            </div>
          ) : null}

          <div className="pt-3" style={{ borderTop: '1px solid var(--border)' }}>
            <p className="text-[10px] font-mono-code uppercase tracking-[0.16em] mb-2.5" style={{ color: 'var(--muted)' }}>
              이 클러스터의 기사 &middot; {clusterPoints.length}
            </p>
            <TopicArticleList points={clusterPoints} />
          </div>

          <button
            onClick={() => onSelectCluster(null)}
            className="mt-4 w-full text-xs rounded-full py-1.5 transition-all"
            style={{ color: 'var(--dim)', border: '1px solid var(--border)', background: 'transparent' }}
          >
            선택 해제
          </button>
        </div>
      ) : (
        <>
          <p
            className="text-[10px] font-mono-code uppercase tracking-[0.18em] px-1"
            style={{ color: 'var(--muted)' }}
          >
            주요 클러스터 &middot; {clusters.length}
          </p>
          <div className="space-y-2">
            {clusters.map((cluster) => (
              <TopicClusterCard
                key={cluster.id}
                cluster={cluster}
                color={clusterColorMap[cluster.id] ?? '#94a3b8'}
                isSelected={selectedClusterId === cluster.id}
                onClick={() => onSelectCluster(cluster.id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
