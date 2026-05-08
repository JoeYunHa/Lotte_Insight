import Link from 'next/link'
import { ArticleFeed } from '@/components/ArticleFeed'
import { LabelBadge } from '@/components/Badges'
import { PageShell } from '@/components/PageShell'
import { getArticles, getPlayers, getTeamReport } from '@/lib/api'
import { ALL_LABELS } from '@/lib/label-config'
import { computeLabelCounts, getTopMentionedPlayersFromArticles } from '@/lib/selectors'
import { formatDateKo, getTodayKST } from '@/lib/time'

export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const today = getTodayKST()

  const [report, articles, players] = await Promise.all([
    getTeamReport(today),
    getArticles({ date: today }),
    getPlayers(),
  ])

  const labelCounts = computeLabelCounts(articles)
  const topPlayers = getTopMentionedPlayersFromArticles(articles, players)

  return (
    <PageShell
      headerAction={{ href: '/archive', label: '아카이브' }}
      seasonBadge="2026 KBO"
      footer={
        <p className="text-xs" style={{ color: 'var(--dim)' }}>
          롯데 인사이트 · 뉴스 원문은 각 출처를 통해 확인하세요.
        </p>
      }
    >
      <div className="pt-10 pb-6">
        <p className="text-xs font-medium mb-3 font-mono-code" style={{ color: 'var(--muted)' }}>
          {formatDateKo(today)}
        </p>
        <h1 className="font-serif-kr text-3xl font-black leading-tight mb-4" style={{ color: 'var(--text)' }}>
          오늘의 롯데
        </h1>
        <div className="h-px w-full mb-4" style={{ background: 'var(--border)' }} />
        {report ? (
          <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
            {report.issue_summary}
          </p>
        ) : (
          <p className="text-sm" style={{ color: 'var(--dim)' }}>
            오늘의 리포트가 아직 생성되지 않았습니다.
          </p>
        )}
      </div>

      <div
        className="rounded-lg p-4 mb-4"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>
            오늘 수집 기사
          </span>
          <span className="font-mono-code text-lg font-bold" style={{ color: 'var(--text)' }}>
            {articles.length}
          </span>
          <span className="text-xs" style={{ color: 'var(--dim)' }}>
            건
          </span>
        </div>
        {articles.length > 0 ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {ALL_LABELS.filter(label => labelCounts[label] > 0).map(label => (
              <div key={label} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--muted)' }}>
                <LabelBadge label={label} />
                <span className="font-mono-code" style={{ color: 'var(--text)' }}>
                  {labelCounts[label]}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs" style={{ color: 'var(--dim)' }}>
            수집된 기사가 없습니다
          </p>
        )}
      </div>

      {topPlayers.length > 0 ? (
        <div className="mb-8">
          <p className="text-xs mb-2.5" style={{ color: 'var(--dim)' }}>
            주요 언급 선수
          </p>
          <div className="flex flex-wrap gap-2">
            {topPlayers.map(({ player, mention_count }) => (
              <Link
                key={player.id}
                href={`/players/${player.id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-sm transition-all hover:-translate-y-px"
                style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
              >
                {player.name}
                <span className="font-mono-code text-xs" style={{ color: 'var(--gold)' }}>
                  {mention_count}회
                </span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      <ArticleFeed articles={articles} />
    </PageShell>
  )
}
