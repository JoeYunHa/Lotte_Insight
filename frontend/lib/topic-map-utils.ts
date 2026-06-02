import { getLabelMeta } from './label-config'
import { clusterPalette, palette } from './palette'
import type { LabelFilter, TopicArticlePoint, TopicCluster, ViewMode } from './types'

export const VIEWBOX_W = 600
export const VIEWBOX_H = 460
export const PADDING = 36

export const CLUSTER_PALETTE = clusterPalette

export type NormalizedPoint = TopicArticlePoint & { svgX: number; svgY: number }

export function normalizePoints(points: TopicArticlePoint[]): NormalizedPoint[] {
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

export function filterPointsByLabel(
  points: NormalizedPoint[],
  labelFilter: LabelFilter,
  clusterById: Record<string, TopicCluster>,
): NormalizedPoint[] {
  if (labelFilter === 'ALL') return points
  return points.filter((p) => {
    const clusterLabel = p.cluster_id ? clusterById[p.cluster_id]?.label_hint : undefined
    return p.article?.primary_label === labelFilter || clusterLabel === labelFilter
  })
}

export function getPointColor(
  p: NormalizedPoint,
  viewMode: ViewMode,
  clusterById: Record<string, TopicCluster>,
  clusterColorMap: Record<string, string>,
): string {
  if (p.is_outlier) return palette.blueDeep
  if (viewMode === 'label') {
    const rawLabel =
      p.article?.primary_label ?? (p.cluster_id ? clusterById[p.cluster_id]?.label_hint : undefined)
    return getLabelMeta(rawLabel)?.dot ?? palette.blueDeep
  }
  if (viewMode === 'outlier') return 'var(--blue-soft-strong)'
  return p.cluster_id ? (clusterColorMap[p.cluster_id] ?? palette.blueDeep) : palette.blueDeep
}

export function getPointOpacity(p: NormalizedPoint, selectedClusterId: string | null): number {
  if (!selectedClusterId) return p.is_outlier ? 0.45 : 0.82
  return p.cluster_id === selectedClusterId ? 1 : 0.1
}

export function isPointClickable(p: NormalizedPoint): boolean {
  return !p.is_outlier && !!p.cluster_id
}

export function findCluster(
  clusters: TopicCluster[],
  clusterId: string | null,
): TopicCluster | null {
  if (!clusterId) return null
  return clusters.find((c) => c.id === clusterId) ?? null
}

export function getClusterPoints(
  points: TopicArticlePoint[],
  clusterId: string,
): TopicArticlePoint[] {
  return points
    .filter((p) => p.cluster_id === clusterId)
    .sort((a, b) => (a.cluster_rank ?? Infinity) - (b.cluster_rank ?? Infinity))
}
