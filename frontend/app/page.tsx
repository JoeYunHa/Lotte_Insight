import { ArticleFeed } from '@/components/ArticleFeed'
import { FeaturedArticleCard } from '@/components/FeaturedArticleCard'
import { HomeHeroDesk } from '@/components/HomeHeroDesk'
import { PageShell } from '@/components/PageShell'
import { RankingPanel } from '@/components/RankingPanel'
import { SectionHeader } from '@/components/SectionHeader'
import { SentimentBar, SignalCard } from '@/components/SignalCard'
import { getArticles, getHomeReport } from '@/lib/api'
import { LABEL_META } from '@/lib/label-config'
import { formatDateKo, formatRelativeTime, getTodayKST } from '@/lib/time'
import type { Article, HomeReport, LabelKey } from '@/lib/types'

export const dynamic = 'force-dynamic'

const ARTICLE_FEED_LIMIT = 30

const LABEL_HEADLINE: Record<LabelKey, string> = {
  MATCH_RELATED: 'Game stories',
  INJURY_ROSTER: 'Roster watch',
  TRANSACTION_CONTRACT: 'Transaction desk',
  PERFORMANCE_ANALYSIS: 'Performance scan',
  INTERVIEW: 'Interview watch',
  CLUB_OPERATION: 'Club bulletin',
  ETC: 'General coverage',
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

  const [homeResult, articlesResult] = await Promise.allSettled([
    getHomeReport(today),
    getArticles({ date: today, limit: ARTICLE_FEED_LIMIT }),
  ])
  const home: HomeReport = homeResult.status === 'fulfilled' ? homeResult.value : emptyHome
  const articles: Article[] = articlesResult.status === 'fulfilled' ? articlesResult.value : []

  const { article_count, label_counts, sentiment, lead_label, lead_summary, top_players, game_context } = home

  const featuredArticle = (lead_label ? articles.find((article) => article.primary_label === lead_label) : null) ?? articles[0] ?? null

  const headline = lead_label
    ? `${LABEL_HEADLINE[lead_label]} are driving today's Lotte conversation`
    : article_count > 0
      ? "A cleaner matchday board for today's Lotte coverage"
      : 'The board is ready for the next Lotte briefing'

  const subcopy =
    article_count > 0
      ? `${article_count} stories are on the desk today. The page now highlights one lead story first, then player and article rankings for faster scanning.`
      : 'No stories have been collected yet. Once the pipeline finishes, the hero card and rankings will fill automatically.'

  const gameKicker = game_context ? `vs ${game_context.opponent} / ${game_context.home_away} / ${game_context.game_time ?? 'TBD'}` : 'SAJIK MATCHDAY BRIEFING'

  const playerRankingRows = top_players.slice(0, 5).map((mention) => ({
    id: String(mention.player.id),
    title: mention.player.name,
    meta: mention.player.position,
    value: String(mention.mention_count),
    href: `/players/${mention.player.id}`,
  }))

  const latestArticleRows = articles.slice(0, 5).map((article) => ({
    id: String(article.id),
    title: article.title,
    meta: `${article.source_name} / ${formatRelativeTime(article.published_at)}`,
    value: article.primary_label ? LABEL_META[article.primary_label].name : 'Desk',
  }))

  return (
    <PageShell
      headerActions={[
        { href: '/players', label: 'Players' },
        { href: '/topics', label: 'Topics' },
        { href: '/archive', label: 'Archive' },
      ]}
      seasonBadge="2026 KBO"
      footer={
        <p className="text-xs" style={{ color: 'var(--dim)' }}>
          Metadata-only fan briefing. Open the original article for full source context.
        </p>
      }
    >
      <HomeHeroDesk date={formatDateKo(today)} headline={headline} subcopy={subcopy} kicker={gameKicker} metaStat={article_count > 0 ? { label: 'stories', value: String(article_count) } : undefined} />

      <section className="mb-10 grid gap-4 lg:grid-cols-[1.45fr_0.95fr]">
        <FeaturedArticleCard article={featuredArticle} />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <SignalCard
            title="Coverage volume"
            eyebrow="Today"
            value={String(article_count)}
            detail={lead_label ? `${label_counts[lead_label]} in ${LABEL_META[lead_label].name}` : 'Waiting for categorized coverage'}
            accent="red"
          />
          <SignalCard title="Mood snapshot" eyebrow="Sentiment" value={sentiment.analyzed > 0 ? `${sentiment.analyzed}` : '0'} detail="Articles with stance data" accent="gold">
            {sentiment.analyzed > 0 ? (
              <SentimentBar positive={sentiment.positive} neutral={sentiment.neutral} negative={sentiment.negative} analyzed={sentiment.analyzed} total={article_count} />
            ) : (
              <p className="mt-3 text-sm leading-7" style={{ color: 'var(--muted)' }}>
                Sentiment bars will appear after the related-news pipeline finishes.
              </p>
            )}
          </SignalCard>
        </div>
      </section>

      <section className="mb-10">
        <SectionHeader label="Quick Rankings" accent="gold" />
        <div className="grid gap-4 xl:grid-cols-3">
          <RankingPanel
            eyebrow="Player rank"
            title="Most-mentioned players"
            rows={playerRankingRows}
            accent="gold"
            emptyTitle="Player ranking is empty"
            emptyBody="Player mention ranking will appear once article-player linking is populated for today."
          />
          <RankingPanel
            eyebrow="Desk board"
            title="Latest headline queue"
            rows={latestArticleRows}
            accent="red"
            emptyTitle="No headlines yet"
            emptyBody="The latest article queue will populate after collection finishes."
          />
          <RankingPanel
            eyebrow="Reader rank"
            title="Most-viewed stories"
            rows={[]}
            accent="neutral"
            emptyTitle="Backend support required"
            emptyBody="The current API does not expose article view counts. A backend note has been written for adding ranked view metrics."
          />
        </div>
      </section>

      {lead_label && lead_summary ? (
        <section className="mb-10">
          <SectionHeader label="Lead Summary" accent="red" />
          <div className="rounded-[24px] p-6" style={{ background: 'rgba(255,255,255,0.72)', border: '1px solid var(--border)' }}>
            <p className="text-sm font-mono-code uppercase tracking-[0.18em]" style={{ color: 'var(--red)' }}>
              {LABEL_META[lead_label].name}
            </p>
            <p className="mt-4 text-base leading-8" style={{ color: 'var(--text)' }}>
              {lead_summary}
            </p>
          </div>
        </section>
      ) : null}

      <section>
        <SectionHeader label="Full Feed" />
        <ArticleFeed articles={articles} />
      </section>
    </PageShell>
  )
}
