import { describe, expect, it } from 'vitest'
import {
  PADDING,
  VIEWBOX_H,
  VIEWBOX_W,
  filterPointsByLabel,
  findCluster,
  getClusterPoints,
  getPointColor,
  getPointOpacity,
  isPointClickable,
  normalizePoints,
} from '../lib/topic-map-utils'
import type { TopicArticlePoint, TopicCluster } from '../lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePoint(overrides: Partial<TopicArticlePoint> = {}): TopicArticlePoint {
  return {
    article_id: 'art-1',
    cluster_id: 'c01',
    cluster_rank: 1,
    x: 0,
    y: 0,
    is_outlier: false,
    article: null,
    ...overrides,
  }
}

function makeCluster(overrides: Partial<TopicCluster> = {}): TopicCluster {
  return {
    id: 'c01',
    map_date: '2026-05-22',
    article_count: 3,
    representative_article_id: null,
    title: '클러스터',
    summary: '요약',
    label_hint: 'MATCH_RELATED',
    key_players: ['전준우'],
    created_at: '2026-05-22T00:00:00Z',
    updated_at: '2026-05-22T00:00:00Z',
    ...overrides,
  }
}

function makeNormalized(overrides: Partial<TopicArticlePoint> = {}) {
  const [p] = normalizePoints([makePoint(overrides)])
  return p
}

// ---------------------------------------------------------------------------
// normalizePoints
// ---------------------------------------------------------------------------

describe('normalizePoints', () => {
  it('returns empty array for empty input', () => {
    expect(normalizePoints([])).toEqual([])
  })

  it('single point maps to center of padded area', () => {
    const [p] = normalizePoints([makePoint({ x: 5, y: 5 })])
    expect(p.svgX).toBe(PADDING)
    expect(p.svgY).toBe(PADDING)
  })

  it('two points: leftmost maps to left edge, rightmost to right edge', () => {
    const pts = normalizePoints([
      makePoint({ article_id: 'a', x: 0, y: 0 }),
      makePoint({ article_id: 'b', x: 1, y: 1 }),
    ])
    expect(pts[0].svgX).toBeCloseTo(PADDING)
    expect(pts[1].svgX).toBeCloseTo(VIEWBOX_W - PADDING)
    expect(pts[0].svgY).toBeCloseTo(PADDING)
    expect(pts[1].svgY).toBeCloseTo(VIEWBOX_H - PADDING)
  })

  it('preserves all original fields', () => {
    const [p] = normalizePoints([makePoint({ article_id: 'xyz', cluster_id: 'c99' })])
    expect(p.article_id).toBe('xyz')
    expect(p.cluster_id).toBe('c99')
  })

  it('handles zero x-range without NaN (degenerate case)', () => {
    const pts = normalizePoints([
      makePoint({ article_id: 'a', x: 3, y: 0 }),
      makePoint({ article_id: 'b', x: 3, y: 1 }),
    ])
    expect(Number.isFinite(pts[0].svgX)).toBe(true)
    expect(Number.isFinite(pts[1].svgX)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// filterPointsByLabel
// ---------------------------------------------------------------------------

describe('filterPointsByLabel', () => {
  const clusterById = { c01: makeCluster({ label_hint: 'MATCH_RELATED' }) }

  it("'ALL' returns all points unchanged", () => {
    const pts = [makeNormalized(), makeNormalized({ article_id: 'art-2', cluster_id: null })]
    expect(filterPointsByLabel(pts, 'ALL', clusterById)).toHaveLength(2)
  })

  it('filters by article primary_label', () => {
    const pts = [
      makeNormalized({ article: { id: 'a', title: 't', source_name: 's', published_at: '', primary_label: 'INJURY_ROSTER' } }),
      makeNormalized({ article_id: 'b', article: { id: 'b', title: 't2', source_name: 's', published_at: '', primary_label: 'MATCH_RELATED' } }),
    ]
    const result = filterPointsByLabel(pts, 'INJURY_ROSTER', clusterById)
    expect(result).toHaveLength(1)
    expect(result[0].article_id).toBe('art-1')
  })

  it('falls back to cluster label_hint when article label is null', () => {
    const pt = makeNormalized({ cluster_id: 'c01', article: null })
    const result = filterPointsByLabel([pt], 'MATCH_RELATED', clusterById)
    expect(result).toHaveLength(1)
  })

  it('excludes points with neither matching article label nor cluster label', () => {
    const pt = makeNormalized({
      article: { id: 'a', title: 't', source_name: 's', published_at: '', primary_label: 'INTERVIEW' },
    })
    expect(filterPointsByLabel([pt], 'INJURY_ROSTER', clusterById)).toHaveLength(0)
  })

  it('outlier with no cluster still participates in article-label match', () => {
    const pt = makeNormalized({
      is_outlier: true,
      cluster_id: null,
      article: { id: 'x', title: 't', source_name: 's', published_at: '', primary_label: 'ETC' },
    })
    expect(filterPointsByLabel([pt], 'ETC', {})).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------
// getPointColor
// ---------------------------------------------------------------------------

describe('getPointColor', () => {
  const cluster = makeCluster({ label_hint: 'MATCH_RELATED' })
  const clusterById = { c01: cluster }
  const colorMap = { c01: '#FF0000' }

  it('outlier always returns slate color regardless of viewMode', () => {
    const p = makeNormalized({ is_outlier: true, cluster_id: 'c01' })
    expect(getPointColor(p, 'cluster', clusterById, colorMap)).toBe('#94a3b8')
    expect(getPointColor(p, 'label', clusterById, colorMap)).toBe('#94a3b8')
    expect(getPointColor(p, 'outlier', clusterById, colorMap)).toBe('#94a3b8')
  })

  it("viewMode='cluster' uses clusterColorMap", () => {
    const p = makeNormalized({ cluster_id: 'c01' })
    expect(getPointColor(p, 'cluster', clusterById, colorMap)).toBe('#FF0000')
  })

  it("viewMode='cluster' falls back to slate when cluster not in colorMap", () => {
    const p = makeNormalized({ cluster_id: 'unknown' })
    expect(getPointColor(p, 'cluster', clusterById, {})).toBe('#94a3b8')
  })

  it("viewMode='label' returns a dot color for known label", () => {
    const p = makeNormalized({
      article: { id: 'a', title: 't', source_name: 's', published_at: '', primary_label: 'MATCH_RELATED' },
    })
    const color = getPointColor(p, 'label', clusterById, colorMap)
    expect(color).not.toBe('#94a3b8')
    expect(color).toMatch(/^#/)
  })

  it("viewMode='label' falls back to cluster label_hint when article label is null", () => {
    const p = makeNormalized({ cluster_id: 'c01', article: null })
    const color = getPointColor(p, 'label', clusterById, colorMap)
    expect(color).not.toBe('#94a3b8')
  })

  it("viewMode='label' returns slate for unknown/null label with no cluster fallback", () => {
    const p = makeNormalized({ cluster_id: null, article: null })
    expect(getPointColor(p, 'label', {}, {})).toBe('#94a3b8')
  })

  it("viewMode='outlier' returns semi-transparent slate for non-outliers", () => {
    const p = makeNormalized({ is_outlier: false })
    expect(getPointColor(p, 'outlier', clusterById, colorMap)).toBe('rgba(148,163,184,0.35)')
  })
})

// ---------------------------------------------------------------------------
// getPointOpacity
// ---------------------------------------------------------------------------

describe('getPointOpacity', () => {
  it('no selection: normal point has 0.82 opacity', () => {
    const p = makeNormalized({ is_outlier: false })
    expect(getPointOpacity(p, null)).toBe(0.82)
  })

  it('no selection: outlier has 0.45 opacity', () => {
    const p = makeNormalized({ is_outlier: true })
    expect(getPointOpacity(p, null)).toBe(0.45)
  })

  it('selected cluster: matched point is fully opaque', () => {
    const p = makeNormalized({ cluster_id: 'c01' })
    expect(getPointOpacity(p, 'c01')).toBe(1)
  })

  it('selected cluster: unmatched point is dimmed', () => {
    const p = makeNormalized({ cluster_id: 'c02' })
    expect(getPointOpacity(p, 'c01')).toBe(0.1)
  })

  it('selected cluster: outlier in different cluster is dimmed', () => {
    const p = makeNormalized({ is_outlier: true, cluster_id: null })
    expect(getPointOpacity(p, 'c01')).toBe(0.1)
  })
})

// ---------------------------------------------------------------------------
// isPointClickable
// ---------------------------------------------------------------------------

describe('isPointClickable', () => {
  it('non-outlier with cluster_id is clickable', () => {
    expect(isPointClickable(makeNormalized({ is_outlier: false, cluster_id: 'c01' }))).toBe(true)
  })

  it('outlier is not clickable', () => {
    expect(isPointClickable(makeNormalized({ is_outlier: true, cluster_id: 'c01' }))).toBe(false)
  })

  it('point without cluster_id is not clickable', () => {
    expect(isPointClickable(makeNormalized({ is_outlier: false, cluster_id: null }))).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// findCluster
// ---------------------------------------------------------------------------

describe('findCluster', () => {
  const clusters = [makeCluster({ id: 'c01' }), makeCluster({ id: 'c02' })]

  it('returns null when clusterId is null', () => {
    expect(findCluster(clusters, null)).toBeNull()
  })

  it('returns matching cluster', () => {
    expect(findCluster(clusters, 'c02')?.id).toBe('c02')
  })

  it('returns null when clusterId not found', () => {
    expect(findCluster(clusters, 'nonexistent')).toBeNull()
  })

  it('returns null for empty clusters array', () => {
    expect(findCluster([], 'c01')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// getClusterPoints
// ---------------------------------------------------------------------------

describe('getClusterPoints', () => {
  it('returns only points belonging to the given cluster', () => {
    const pts = [
      makePoint({ article_id: 'a', cluster_id: 'c01', cluster_rank: 1 }),
      makePoint({ article_id: 'b', cluster_id: 'c02', cluster_rank: 1 }),
      makePoint({ article_id: 'c', cluster_id: 'c01', cluster_rank: 2 }),
    ]
    const result = getClusterPoints(pts, 'c01')
    expect(result.map((p) => p.article_id)).toEqual(['a', 'c'])
  })

  it('sorts by cluster_rank ascending', () => {
    const pts = [
      makePoint({ article_id: 'b', cluster_id: 'c01', cluster_rank: 3 }),
      makePoint({ article_id: 'a', cluster_id: 'c01', cluster_rank: 1 }),
      makePoint({ article_id: 'c', cluster_id: 'c01', cluster_rank: 2 }),
    ]
    const result = getClusterPoints(pts, 'c01')
    expect(result.map((p) => p.article_id)).toEqual(['a', 'c', 'b'])
  })

  it('null cluster_rank sorts to end (treated as Infinity)', () => {
    const pts = [
      makePoint({ article_id: 'null-rank', cluster_id: 'c01', cluster_rank: null }),
      makePoint({ article_id: 'ranked', cluster_id: 'c01', cluster_rank: 1 }),
    ]
    const result = getClusterPoints(pts, 'c01')
    expect(result[0].article_id).toBe('ranked')
    expect(result[1].article_id).toBe('null-rank')
  })

  it('returns empty array when no points match', () => {
    expect(getClusterPoints([makePoint({ cluster_id: 'c02' })], 'c01')).toHaveLength(0)
  })

  it('does not mutate original array order', () => {
    const pts = [
      makePoint({ article_id: 'b', cluster_id: 'c01', cluster_rank: 2 }),
      makePoint({ article_id: 'a', cluster_id: 'c01', cluster_rank: 1 }),
    ]
    getClusterPoints(pts, 'c01')
    expect(pts[0].article_id).toBe('b')
  })
})
