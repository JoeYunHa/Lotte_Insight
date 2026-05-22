import Link from 'next/link'
import { PageShell } from '@/components/PageShell'
import { SectionHeader } from '@/components/SectionHeader'
import { getPlayers } from '@/lib/api'
import type { Player, PlayerStatus } from '@/lib/types'

export const dynamic = 'force-dynamic'

const POSITION_GROUPS: { key: string; label: string; match: (p: string) => boolean }[] = [
  { key: 'pitcher',  label: '투수',  match: p => p.includes('투수') || p.includes('마무리') || p.includes('선발') || p.includes('중계') },
  { key: 'catcher',  label: '포수',  match: p => p.includes('포수') },
  { key: 'infield',  label: '내야수', match: p => p.includes('내야') || ['1루','2루','3루','유격'].some(k => p.includes(k)) },
  { key: 'outfield', label: '외야수', match: p => p.includes('외야') || ['좌익','중견','우익','좌翼','중견수'].some(k => p.includes(k)) },
]

function classifyPosition(position: string): string {
  for (const g of POSITION_GROUPS) {
    if (g.match(position)) return g.key
  }
  return 'etc'
}

function groupPlayers(players: Player[]) {
  const groups: Record<string, Player[]> = {
    pitcher: [], catcher: [], infield: [], outfield: [], etc: [],
  }
  for (const p of players) {
    groups[classifyPosition(p.position)].push(p)
  }
  return groups
}

const STATUS_STYLE: Record<PlayerStatus, { label: string; color: string }> = {
  active: { label: '1군', color: 'var(--gold)' },
  '1군': { label: '1군', color: 'var(--gold)' },
  '2군': { label: '2군', color: 'var(--dim)' },
  '말소': { label: '말소', color: 'var(--dim)' },
}

function isActiveStatus(status: string): boolean {
  return status === 'active' || status === '1군'
}

function PlayerCard({ player }: { player: Player }) {
  const statusStyle = STATUS_STYLE[player.status] ?? { label: player.status, color: 'var(--dim)' }
  const isActive = isActiveStatus(player.status)

  return (
    <Link
      href={`/players/${player.id}`}
      className="block rounded-lg p-3.5 transition-all duration-200 group"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        opacity: isActive ? 1 : 0.55,
      }}
    >
      <div className="flex items-center gap-3">
        {/* Jersey number */}
        <span
          className="text-lg font-bold font-mono-code leading-none w-8 shrink-0 text-center"
          style={{ color: isActive ? 'var(--gold)' : 'var(--dim)' }}
        >
          {player.number ?? '—'}
        </span>

        {/* Name + position */}
        <div className="flex-1 min-w-0">
          <p
            className="font-bold text-sm leading-tight transition-colors group-hover:text-lotte-red truncate"
            style={{ color: 'var(--text)' }}
          >
            {player.name}
          </p>
          <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--dim)' }}>
            {player.position}
          </p>
        </div>

        {/* Status badge */}
        <span
          className="text-[10px] font-mono-code font-bold shrink-0"
          style={{ color: statusStyle.color }}
        >
          {statusStyle.label}
        </span>
      </div>
    </Link>
  )
}

export default async function PlayersPage() {
  let players: Player[] = []
  try {
    players = await getPlayers()
  } catch {
    players = []
  }
  const groups = groupPlayers(players)
  const activeCount = players.filter((p) => isActiveStatus(p.status)).length

  return (
    <PageShell headerActions={[{ href: '/', label: '오늘 리포트' }, { href: '/archive', label: '아카이브' }]}>
      <div className="pt-10 pb-6">
        <p className="text-xs font-medium mb-3 font-mono-code" style={{ color: 'var(--muted)' }}>
          2026 KBO 시즌
        </p>
        <h1 className="font-serif-kr text-3xl font-black leading-tight mb-1" style={{ color: 'var(--text)' }}>
          롯데 선수단
        </h1>
        <p className="text-sm mb-4" style={{ color: 'var(--dim)' }}>
          1군 {activeCount}명 · 전체 {players.length}명
        </p>
        <div className="h-px w-full" style={{ background: 'var(--border)' }} />
      </div>

      {players.length === 0 ? (
        <p className="text-sm py-16 text-center" style={{ color: 'var(--dim)' }}>
          등록된 선수 데이터가 없습니다.
        </p>
      ) : (
        POSITION_GROUPS.map(group => {
          const list = groups[group.key]
          if (list.length === 0) return null
          const sorted = [...list].sort((a, b) => {
            if (isActiveStatus(a.status) && !isActiveStatus(b.status)) return -1
            if (!isActiveStatus(a.status) && isActiveStatus(b.status)) return 1
            const na = Number(a.number) || 999
            const nb = Number(b.number) || 999
            return na - nb
          })
          return (
            <section key={group.key} className="mb-10">
              <SectionHeader label={group.label} />
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {sorted.map(player => (
                  <PlayerCard key={player.id} player={player} />
                ))}
              </div>
            </section>
          )
        })
      )}

      {groups.etc.length > 0 && (
        <section className="mb-10">
          <SectionHeader label="기타" />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {groups.etc.map(player => (
              <PlayerCard key={player.id} player={player} />
            ))}
          </div>
        </section>
      )}
    </PageShell>
  )
}
