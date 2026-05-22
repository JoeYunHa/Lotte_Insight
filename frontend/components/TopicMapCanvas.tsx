'use client'

import { useMemo, useState } from 'react'
import { getLabelMeta } from '@/lib/label-config'
import type { TopicArticlePoint, TopicCluster } from '@/lib/types'
import type { LabelFilter, ViewMode } from './TopicMapToolbar'

const VIEWBOX_W = 600
const VIEWBOX_H = 460
const PADDING = 36

export const CLUSTER_PALETTE = [
  '#E1062C',
  '#D97706',
  '#7C3AED',
  '#0D9488',
  '#6366F1',
  '#EC4899',
  '#059669',
  '#0891B2',
  '#F59E0B',
  '#DC2626',
]

type NormalizedPoint = TopicArticlePoint & { svgX: number; svgY: number }

function normalize(points: TopicArticlePoint[]): NormalizedPoint[] {
  if (points.length === 0) return []
  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const rangeX = maxX - minX || 1
  const rangeY = maxY - minY || 1

  return points.map((p) => ({
    ...p,
    svgX: PADDING + ((p.x - minX) / rangeX) * (VIEWBOX_W - 2 * PADDING),
    svgY: PADDING + ((p.y - minY) / rangeY) * (VIEWBOX_H - 2 * PADDING),
  }))
}

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

  const normalized = useMemo(() => normalize(points), [points])

  const visiblePoints = useMemo(() => {
    if (labelFilter === 'ALL') return normalized
    return normalized.filter((p) => {
      const clusterLabel = p.cluster_id ? clusterById[p.cluster_id]?.label_hint : undefined
      return p.article?.primary_label === labelFilter || clusterLabel === labelFilter
    })
  }, [normalized, labelFilter, clusterById])

  const representativeIds = useMemo(
    () => new Set(clusters.map((c) => c.representative_article_id).filter(Boolean)),
    [clusters]
  )

  function getColor(p: NormalizedPoint): string {
    if (p.is_outlier) return '#94a3b8'
    if (viewMode === 'label') {
      const rawLabel = p.article?.primary_label ?? (p.cluster_id ? clusterById[p.cluster_id]?.label_hint : undefined)
      return getLabelMeta(rawLabel)?.dot ?? '#94a3b8'
    }
    if (viewMode === 'outlier') return p.is_outlier ? '#E1062C' : 'rgba(148,163,184,0.35)'
    return p.cluster_id ? (clusterColorMap[p.cluster_id] ?? '#94a3b8') : '#94a3b8'
  }

  function getOpacity(p: NormalizedPoint): number {
    if (!selectedClusterId) return p.is_outlier ? 0.45 : 0.82
    return p.cluster_id === selectedClusterId ? 1 : 0.1
  }

  const isClickable = (p: NormalizedPoint) => !p.is_outlier && !!p.cluster_id

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
