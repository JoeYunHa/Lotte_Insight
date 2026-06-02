import { getLabelMeta, getToneBadgeStyle } from '@/lib/label-config'
import type { TopicCluster } from '@/lib/types'

interface TopicClusterCardProps {
  cluster: TopicCluster
  color: string
  isSelected: boolean
  onClick: () => void
}

export function TopicClusterCard({ cluster, color, isSelected, onClick }: TopicClusterCardProps) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl p-4 transition-all duration-200"
      style={{
        background: isSelected ? 'var(--surface-overlay-strong)' : 'var(--surface)',
        border: isSelected ? `1.5px solid ${color}` : '1px solid var(--border)',
        boxShadow: isSelected ? `0 4px 20px color-mix(in srgb, ${color} 24%, transparent)` : 'none',
      }}
    >
      <div className="flex items-start gap-3">
        <span
          className="shrink-0 w-2.5 h-2.5 rounded-full"
          style={{ background: color, marginTop: '3px' }}
        />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
            <span className="text-[11px] font-mono-code" style={{ color: 'var(--muted)' }}>
              {cluster.article_count}개 기사
            </span>
            {(() => { const meta = getLabelMeta(cluster.label_hint); return meta ? (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={getToneBadgeStyle(meta.tone)}>
                {meta.name}
              </span>
            ) : null })()}
          </div>

          <p className="text-sm font-semibold leading-snug mb-1.5" style={{ color: 'var(--text)' }}>
            {cluster.title}
          </p>

          <p className="text-xs leading-5 line-clamp-2" style={{ color: 'var(--muted)' }}>
            {cluster.summary}
          </p>

          {cluster.key_players.length > 0 ? (
            <div className="flex flex-wrap gap-1 mt-2">
              {cluster.key_players.slice(0, 3).map((name) => (
                <span
                  key={name}
                  className="text-[10px] px-1.5 py-0.5 rounded-full"
                  style={{ background: 'var(--surface-2)', color: 'var(--dim)', border: '1px solid var(--border)' }}
                >
                  {name}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </button>
  )
}
