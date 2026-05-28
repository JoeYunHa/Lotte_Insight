'use client'

import { useMemo, useState } from 'react'
import { TopicClusterPanel } from './TopicClusterPanel'
import { TopicMapCanvas, CLUSTER_PALETTE } from './TopicMapCanvas'
import { TopicMapToolbar } from './TopicMapToolbar'
import type { LabelFilter, ViewMode } from './TopicMapToolbar'
import type { TopicMapData } from '@/lib/types'

interface TopicMapExplorerProps {
  data: TopicMapData
}

export function TopicMapExplorer({ data }: TopicMapExplorerProps) {
  const { clusters, points } = data

  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('cluster')
  const [labelFilter, setLabelFilter] = useState<LabelFilter>('ALL')

  const clusterColorMap = useMemo(() => {
    const map: Record<string, string> = {}
    clusters.forEach((c, i) => {
      map[c.id] = CLUSTER_PALETTE[i % CLUSTER_PALETTE.length]
    })
    return map
  }, [clusters])

  const hasOutliers = points.some((p) => p.is_outlier)

  const outlierCount = points.filter((p) => p.is_outlier).length
  const largestCluster = clusters.reduce(
    (max, c) => (c.article_count > max ? c.article_count : max),
    0
  )

  function handleReset() {
    setSelectedClusterId(null)
    setViewMode('cluster')
    setLabelFilter('ALL')
  }

  return (
    <div>
      {/* 2-column layout on lg+, stacked below */}
      <div className="grid gap-5 lg:grid-cols-[1.5fr_0.9fr]">
        {/* Left pane: toolbar + canvas + stats bar */}
        <div className="flex flex-col gap-3">
          <TopicMapToolbar
            labelFilter={labelFilter}
            viewMode={viewMode}
            hasOutliers={hasOutliers}
            onLabelFilter={(f) => { setLabelFilter(f); setSelectedClusterId(null) }}
            onViewMode={setViewMode}
            onReset={handleReset}
          />

          <div
            className="rounded-[24px] overflow-hidden"
            style={{
              border: '1px solid var(--border)',
              boxShadow: '0 2px 24px rgba(96,62,27,0.07)',
            }}
          >
            <TopicMapCanvas
              clusters={clusters}
              points={points}
              clusterColorMap={clusterColorMap}
              selectedClusterId={selectedClusterId}
              viewMode={viewMode}
              labelFilter={labelFilter}
              onSelectCluster={setSelectedClusterId}
            />
          </div>

          {/* Bottom stats bar */}
          {clusters.length > 0 ? (
            <div
              className="rounded-2xl px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-1.5"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <span className="text-xs font-mono-code" style={{ color: 'var(--muted)' }}>
                <span style={{ color: 'var(--text)', fontWeight: 700 }}>{clusters.length}</span> clusters
              </span>
              {largestCluster > 0 ? (
                <span className="text-xs font-mono-code" style={{ color: 'var(--muted)' }}>
                  largest cluster{' '}
                  <span style={{ color: 'var(--text)', fontWeight: 700 }}>{largestCluster}</span> stories
                </span>
              ) : null}
              {outlierCount > 0 ? (
                <span className="text-xs font-mono-code" style={{ color: 'var(--muted)' }}>
                  <span style={{ color: 'var(--text)', fontWeight: 700 }}>{outlierCount}</span> outliers
                </span>
              ) : null}
              <span className="text-xs" style={{ color: 'var(--dim)' }}>
                &mdash; Click a point to explore its cluster
              </span>
            </div>
          ) : null}
        </div>

        {/* Right pane: cluster reading panel */}
        <div className="lg:max-h-[680px] lg:overflow-y-auto">
          <TopicClusterPanel
            clusters={clusters}
            points={points}
            clusterColorMap={clusterColorMap}
            selectedClusterId={selectedClusterId}
            onSelectCluster={setSelectedClusterId}
          />
        </div>
      </div>
    </div>
  )
}
