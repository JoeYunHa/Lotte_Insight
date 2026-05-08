import { notFound } from 'next/navigation'
import { ArticleCard } from '@/components/ArticleCard'
import { PageShell } from '@/components/PageShell'
import { PlayerIdentityHeader, PlayerStatsCard } from '@/components/PlayerStatsCard'
import { getArticles, getPlayer, getPlayerReport } from '@/lib/api'
import { getTodayKST } from '@/lib/time'

export const revalidate = 300

interface Props {
  params: Promise<{ id: string }>
}

export default async function PlayerPage({ params }: Props) {
  const { id } = await params
  const today = getTodayKST()

  const [player, report, playerArticles] = await Promise.all([
    getPlayer(id, today),
    getPlayerReport(id, today),
    getArticles({ player_id: id, limit: 10 }),
  ])

  if (!player) notFound()

  const stats = player.stats?.[0] ?? null

  return (
    <PageShell headerAction={{ href: '/', label: '오늘 리포트' }}>
      <PlayerIdentityHeader
        playerName={player.name}
        playerNumber={player.number}
        playerPosition={player.position}
        playerStatus={player.status}
      />

      <PlayerStatsCard
        stats={stats}
        statsDate={today}
      />

      <div className="mb-8">
        <p className="text-xs mb-2" style={{ color: 'var(--dim)' }}>
          오늘의 리포트
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
              오늘의 리포트가 아직 생성되지 않았습니다.
            </p>
          )}
        </div>
      </div>

      <div>
        <p className="text-xs mb-3" style={{ color: 'var(--dim)' }}>
          최근 기사 ({playerArticles.length}건)
        </p>
        {playerArticles.length > 0 ? (
          <div className="space-y-2.5">
            {playerArticles.map(article => (
              <ArticleCard
                key={article.id}
                article={article}
                variant="compact"
                showKeyPlayers={false}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm py-8 text-center" style={{ color: 'var(--dim)' }}>
            최근 기사가 없습니다
          </p>
        )}
      </div>
    </PageShell>
  )
}
