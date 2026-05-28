'use client'

import { useMemo, useState } from 'react'
import {
  CLUSTER_PALETTE,
  VIEWBOX_H,
  VIEWBOX_W,
  filterPointsByLabel,
  getPointColor,
  getPointOpacity,
  isPointClickable,
  normalizePoints,
  type NormalizedPoint,
} from '@/lib/topic-map-utils'
import type { TopicArticlePoint, TopicCluster } from '@/lib/types'
import type { LabelFilter, ViewMode } from './TopicMapToolbar'

export { CLUSTER_PALETTE }

interface Props {
  clusters: TopicCluster[]
  points: TopicArticlePoint[]
  clusterColorMap: Record<string, string>
  selectedClusterId: string | null
  viewMode: ViewMode
  labelFilter: LabelFilter
  onSelectCluster: (clusterId: string | null) => void
}

export function TopicMapCanvas({
  clusters,
  points,
  clusterColorMap,
  selectedClusterId,
  viewMode,
  labelFilter,
  onSelectCluster,
}: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  // O(1) cluster lookup — avoids O(N·M) find() calls per render
  const clusterById = useMemo(() => {
    const map: Record<string, TopicCluster> = {}
    clusters.forEach((c) => { map[c.id] = c })
    return map
  }, [clusters])

  const normalized = useMemo(() => normalizePoints(points), [points])

  const visiblePoints = useMemo(
    () => filterPointsByLabel(normalized, labelFilter, clusterById),
    [normalized, labelFilter, clusterById],
  )

  const representativeIds = useMemo(
    () => new Set(clusters.map((c) => c.representative_article_id).filter(Boolean)),
    [clusters]
  )

  const getColor = (p: NormalizedPoint) => getPointColor(p, viewMode, clusterById, clusterColorMap)
  const getOpacity = (p: NormalizedPoint) => getPointOpacity(p, selectedClusterId)
  const isClickable = isPointClickable

  return (
    <div
      className="w-full overflow-hidden"
      style={{
        background:
          'radial-gradient(ellipse at 20% 30%, rgba(241,232,218,0.55) 0%, rgba(251,246,239,0.8) 60%)',
        borderRadius: '16px',
        border: '1px solid var(--border)',
      }}
    >
      <svg
        viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
        className="w-full h-full block"
        aria-label="Topic map scatter plot"
      >
        <defs>
          <pattern id="dot-grid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="10" cy="10" r="0.7" fill="rgba(96,62,27,0.09)" />
          </pattern>
        </defs>
        <rect width={VIEWBOX_W} height={VIEWBOX_H} fill="url(#dot-grid)" rx="16" />

        {visiblePoints.map((p) => {
          const color = getColor(p)
          const opacity = getOpacity(p)
          const isHovered = hoveredId === p.article_id
          const isInSelected = p.cluster_id === selectedClusterId && selectedClusterId !== null
          const isRep = representativeIds.has(p.article_id)
          const clickable = isClickable(p)

          const r = isHovered ? 7 : isInSelected ? 6 : p.is_outlier ? 3 : 5

          return (
            <g
              key={p.article_id}
              style={{ cursor: clickable ? 'pointer' : 'default' }}
              onMouseEnter={() => setHoveredId(p.article_id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => {
                if (!clickable) return
                onSelectCluster(p.cluster_id === selectedClusterId ? null : p.cluster_id!)
              }}
            >
              {isHovered && clickable && (
                <circle cx={p.svgX} cy={p.svgY} r={r + 7} fill={color} opacity={0.18} />
              )}
              {isRep && (
                <circle
                  cx={p.svgX}
                  cy={p.svgY}
                  r={r + 3}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  opacity={opacity}
                />
              )}
              <circle cx={p.svgX} cy={p.svgY} r={r} fill={color} opacity={opacity} />
              {p.article && <title>{p.article.title}</title>}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
