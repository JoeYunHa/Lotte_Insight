import { notFound } from 'next/navigation'
import { ArticleCard } from '@/components/ArticleCard'
import { PageShell } from '@/components/PageShell'
import { PlayerIdentityHeader, PlayerStatsCard } from '@/components/PlayerStatsCard'
import { getArticles, getPlayer, getPlayerReport } from '@/lib/api'
import type { Article, PlayerDailyReport, PlayerDetail } from '@/lib/types'
import { getTodayKST } from '@/lib/time'

export const dynamic = 'force-dynamic'

interface Props {
  params: Promise<{ id: string }>
}

export default async function PlayerPage({ params }: Props) {
  const { id } = await params
  const today = getTodayKST()

  let player: PlayerDetail | null = null
  try {
    player = await getPlayer(id, today)
  } catch {
    notFound()
  }
  if (!player) notFound()

  // Optional sections should never force a 404.
  let report: PlayerDailyReport | null = null
  let playerArticles: Article[] = []
  try {
    ;[report, playerArticles] = await Promise.all([getPlayerReport(id, today), getArticles({ player_id: id, limit: 10 })])
  } catch {
    report = null
    playerArticles = []
  }

  const stats = player.stats?.[0] ?? null

  return (
    <PageShell headerActions={[{ href: '/players', label: 'Players' }, { href: '/', label: 'Today' }]}>
      <PlayerIdentityHeader playerName={player.name} playerNumber={player.number} playerPosition={player.position} playerStatus={player.status} />

      <PlayerStatsCard stats={stats} statsDate={today} />

      <div className="mb-8">
        <p className="text-xs mb-2" style={{ color: 'var(--dim)' }}>
          Today&apos;s player report
        </p>
        <div
          className="rounded-lg p-4"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderLeft: '3px solid var(--red)',
          }}
        >
          {report ? (
            <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
              {report.insight}
            </p>
          ) : (
            <p className="text-sm" style={{ color: 'var(--dim)' }}>
              Report is not generated yet for this date.
            </p>
          )}
        </div>
      </div>

      <div>
        <p className="text-xs mb-3" style={{ color: 'var(--dim)' }}>
          Recent stories ({playerArticles.length})
        </p>
        {playerArticles.length > 0 ? (
          <div className="space-y-2.5">
            {playerArticles.map((article) => (
              <ArticleCard key={article.id} article={article} variant="compact" showKeyPlayers={false} />
            ))}
          </div>
        ) : (
          <p className="text-sm py-8 text-center" style={{ color: 'var(--dim)' }}>
            No recent stories found.
          </p>
        )}
      </div>
    </PageShell>
  )
}
