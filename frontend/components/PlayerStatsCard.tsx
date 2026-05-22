import { formatDate } from '@/lib/time'
import type { PlayerStatDaily, PlayerStatus } from '@/lib/types'

interface PlayerStatsCardProps {
  stats: PlayerStatDaily | null
  statsDate: string
}

interface StatField {
  label: string
  value: string
}

const STATUS_COLOR: Record<PlayerStatus, { bg: string; text: string; border: string }> = {
  active: { bg: 'rgba(52,211,153,0.12)', text: '#34d399', border: 'rgba(52,211,153,0.25)' },
  '1군': { bg: 'rgba(52,211,153,0.12)', text: '#34d399', border: 'rgba(52,211,153,0.25)' },
  '2군': { bg: 'rgba(148,163,184,0.12)', text: '#94a3b8', border: 'rgba(148,163,184,0.25)' },
  '말소': { bg: 'rgba(248,113,113,0.12)', text: '#f87171', border: 'rgba(248,113,113,0.25)' },
}

export function PlayerIdentityHeader({
  playerNumber,
  playerPosition,
  playerStatus,
  playerName,
}: {
  playerNumber?: string | null
  playerPosition: string
  playerStatus: PlayerStatus
  playerName: string
}) {
  const statusColor = STATUS_COLOR[playerStatus]

  return (
    <div className="pt-10 pb-6">
      <div className="flex items-center gap-2 mb-1">
        {playerNumber ? (
          <span
            className="text-xs font-mono-code px-2 py-0.5 rounded"
            style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
          >
            #{playerNumber}
          </span>
        ) : null}
        <span className="text-xs" style={{ color: 'var(--muted)' }}>
          {playerPosition}
        </span>
        <span
          className="text-xs px-2 py-0.5 rounded"
          style={{
            background: statusColor.bg,
            color: statusColor.text,
            border: `1px solid ${statusColor.border}`,
          }}
        >
          {playerStatus === 'active' ? '1군' : playerStatus}
        </span>
      </div>
      <h1 className="font-serif-kr text-3xl font-black my-2" style={{ color: 'var(--text)' }}>
        {playerName}
      </h1>
      <div className="h-px w-full mt-4" style={{ background: 'var(--border)' }} />
    </div>
  )
}

export function PlayerStatsCard({
  stats,
  statsDate,
}: PlayerStatsCardProps) {
  if (!stats) {
    return (
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <p className="text-xs" style={{ color: 'var(--dim)' }}>
          기록 데이터 없음
        </p>
      </div>
    )
  }

  const statFields = getStatFields(stats)

  return (
    <div
      className="rounded-lg p-4 mb-6"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <p className="text-xs mb-3" style={{ color: 'var(--dim)' }}>
        시즌 기록 · {formatDate(statsDate)}
      </p>
      <div className="flex gap-6 flex-wrap">
        {statFields.map(field => (
          <StatItem key={field.label} label={field.label} value={field.value} />
        ))}
      </div>
    </div>
  )
}

function getStatFields(stats: PlayerStatDaily): StatField[] {
  const rawStats = stats.raw_stats as Record<string, unknown>

  if (stats.avg != null || stats.ops != null) {
    return [
      stats.avg != null ? { label: '타율', value: stats.avg.toFixed(3) } : null,
      stats.ops != null ? { label: 'OPS', value: stats.ops.toFixed(3) } : null,
      rawStats.rbi != null ? { label: '타점', value: String(rawStats.rbi) } : null,
    ].filter((field): field is StatField => field !== null)
  }

  return [
    stats.era != null ? { label: 'ERA', value: stats.era.toFixed(2) } : null,
    rawStats.sv != null ? { label: '세이브', value: String(rawStats.sv) } : null,
    rawStats.k != null ? { label: '탈삼진', value: String(rawStats.k) } : null,
  ].filter((field): field is StatField => field !== null)
}

function StatItem({ label, value }: StatField) {
  return (
    <div>
      <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>
        {label}
      </p>
      <p className="font-mono-code text-2xl font-bold" style={{ color: 'var(--text)' }}>
        {value}
      </p>
    </div>
  )
}
