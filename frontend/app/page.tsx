import { ArticleFeed } from '@/components/ArticleFeed'
import { PageShell } from '@/components/PageShell'
import { HomeHeroDesk } from '@/components/HomeHeroDesk'
import { SignalCard, SentimentBar } from '@/components/SignalCard'
import { LeadIssueCard } from '@/components/LeadIssueCard'
import { HotPlayerCard } from '@/components/HotPlayerCard'
import { SectionHeader } from '@/components/SectionHeader'
import { getArticles, getHomeReport } from '@/lib/api'
import { LABEL_META } from '@/lib/label-config'
import { formatDateKo, getTodayKST } from '@/lib/time'
import type { Article, HomeReport, LabelKey } from '@/lib/types'

export const dynamic = 'force-dynamic'

const ARTICLE_FEED_LIMIT = 30

const LABEL_HEADLINE: Record<LabelKey, string> = {
  MATCH_RELATED:        '경기 이슈',
  INJURY_ROSTER:        '부상·엔트리 이슈',
  TRANSACTION_CONTRACT: '거래·계약 이슈',
  PERFORMANCE_ANALYSIS: '성적 분석',
  INTERVIEW:            '선수단 인터뷰',
  CLUB_OPERATION:       '구단 운영 이슈',
  ETC:                  '여러 이슈',
}

export default async function HomePage() {
  const today = getTodayKST()

  const emptyHome: HomeReport = {
    date: today,
    article_count: 0,
    label_counts: {
      MATCH_RELATED: 0,
      INJURY_ROSTER: 0,
      TRANSACTION_CONTRACT: 0,
      PERFORMANCE_ANALYSIS: 0,
      INTERVIEW: 0,
      CLUB_OPERATION: 0,
      ETC: 0,
    },
    sentiment: { positive: 0, neutral: 0, negative: 0, analyzed: 0 },
    lead_label: null,
    lead_summary: null,
    lead_key_players: [],
    top_players: [],
    team_report: null,
    game_context: null,
  }

  let home: HomeReport = emptyHome
  let articles: Article[] = []
  try {
    const result = await Promise.all([
      getHomeReport(today),
      getArticles({ date: today, limit: ARTICLE_FEED_LIMIT }),
    ])
    home = result[0]
    articles = result[1]
  } catch {
    home = emptyHome
    articles = []
  }

  const {
    article_count,
    label_counts,
    sentiment,
    lead_label,
    lead_summary,
    lead_key_players,
    top_players,
    game_context,
  } = home

  const headline = lead_label
    ? `오늘 롯데 여론은 ${LABEL_HEADLINE[lead_label]}가 지배했다`
    : article_count > 0
      ? '오늘 롯데 자이언츠 이슈를 정리했습니다'
      : '아직 수집된 기사가 없습니다'

  const topPlayerName = top_players[0]?.player.name
  const subcopy =
    article_count === 0
      ? '오늘 수집된 기사가 아직 없습니다.'
      : lead_label
        ? `기사 ${article_count}건 수집, ${label_counts[lead_label]}건이 ${LABEL_META[lead_label].name} 관련${topPlayerName ? `이며 ${topPlayerName} 언급량이 가장 높았습니다.` : '.'}`
        : `총 ${article_count}건의 기사가 수집됐습니다.`

  const gameKicker = game_context
    ? `vs ${game_context.opponent} · ${game_context.home_away} · ${game_context.game_time ?? ''}`
    : 'MATCHDAY BRIEFING'

  return (
    <PageShell
      headerActions={[{ href: '/players', label: '선수단' }, { href: '/archive', label: '아카이브' }]}
      seasonBadge="2026 KBO"
      footer={
        <p className="text-xs" style={{ color: 'var(--dim)' }}>
          비공식 팬 서비스 · 롯데 인사이트 · 뉴스 원문은 각 출처에서 확인하세요
        </p>
      }
    >
      {/* 1. Hero Desk */}
      <HomeHeroDesk
        date={formatDateKo(today)}
        headline={headline}
        subcopy={subcopy}
        kicker={gameKicker}
        metaStat={article_count > 0 ? { label: 'TODAY', value: String(article_count) } : undefined}
      />

      {/* 2. Matchday Signals */}
      <section className="mb-12">
        <SectionHeader label="MATCHDAY SIGNALS" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SignalCard
            title="수집 기사"
            value={String(article_count)}
            detail="건"
            delay={0}
          />
          <SignalCard
            title="핵심 이슈"
            value={lead_label ? LABEL_META[lead_label].name : '—'}
            detail={lead_label ? `${label_counts[lead_label]}건` : undefined}
            delay={80}
            accent="red"
          />
          <SignalCard
            title="최다 언급"
            value={top_players[0]?.player.name ?? '—'}
            detail={top_players[0] ? `${top_players[0].mention_count}회` : undefined}
            delay={160}
            accent="gold"
          />
          <SignalCard
            title="여론 온도"
            value={sentiment.analyzed > 0 ? '' : '—'}
            delay={240}
          >
            {sentiment.analyzed > 0 ? (
              <SentimentBar
                positive={sentiment.positive}
                neutral={sentiment.neutral}
                negative={sentiment.negative}
                analyzed={sentiment.analyzed}
                total={article_count}
              />
            ) : (
              <p className="text-xs mt-1" style={{ color: 'var(--dim)' }}>분석 대기중</p>
            )}
          </SignalCard>
        </div>
      </section>

      {/* 3. Lead Story */}
      {lead_label ? (
        <section className="mb-12">
          <SectionHeader label="LEAD STORY" accent="red" />
          <LeadIssueCard
            label={lead_label}
            summary={lead_summary ?? ''}
            articleCount={label_counts[lead_label]}
            keyPlayers={lead_key_players}
          />
        </section>
      ) : null}

      {/* 4. Hot Players */}
      {top_players.length > 0 ? (
        <section className="mb-12">
          <SectionHeader label="HOT PLAYERS" accent="gold" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {top_players.map((pm, i) => (
              <HotPlayerCard
                key={pm.player.id}
                playerMention={pm}
                rank={i + 1}
                delay={i * 60}
                highlight={i === 0}
              />
            ))}
          </div>
        </section>
      ) : null}

      {/* 5. Article Feed */}
      <section>
        <SectionHeader label="DESK FILES" />
        <ArticleFeed articles={articles} />
      </section>
    </PageShell>
  )
}
