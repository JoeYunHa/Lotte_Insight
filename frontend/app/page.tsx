import { ArticleFeed } from "@/components/ArticleFeed";
import { FanVoiceLayer } from "@/components/FanVoice/FanVoiceLayer";
import { FeaturedArticleCard } from "@/components/FeaturedArticleCard";
import { HomeHeroDesk } from "@/components/HomeHeroDesk";
import { PageShell } from "@/components/Page/PageShell";
import { RankingPanel } from "@/components/RankingPanel";
import { SectionHeader } from "@/components/SectionHeader";
import { SentimentBar, SignalCard } from "@/components/SignalCard";
import { getArticles, getHomeReport } from "@/lib/api";
import { LABEL_META } from "@/lib/label-config";
import { formatDateKo, formatRelativeTime, getTodayKST } from "@/lib/time";
import type { Article, HomeReport, LabelKey } from "@/lib/types";

export const dynamic = "force-dynamic";

const ARTICLE_FEED_LIMIT = 30;

const LABEL_HEADLINE: Record<LabelKey, string> = {
  MATCH_RELATED: "경기 소식",
  INJURY_ROSTER: "엔트리 동향",
  TRANSACTION_CONTRACT: "트레이드·계약",
  PERFORMANCE_ANALYSIS: "성적 분석",
  INTERVIEW: "인터뷰",
  CLUB_OPERATION: "구단 소식",
  ETC: "일반 소식",
};

export default async function HomePage() {
  const today = getTodayKST();

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
  };

  const [homeResult, articlesResult] = await Promise.allSettled([
    getHomeReport(today),
    getArticles({ date: today, limit: ARTICLE_FEED_LIMIT }),
  ]);
  const home: HomeReport =
    homeResult.status === "fulfilled" ? homeResult.value : emptyHome;
  const articles: Article[] =
    articlesResult.status === "fulfilled" ? articlesResult.value : [];

  const {
    article_count,
    label_counts,
    sentiment,
    lead_label,
    lead_summary,
    top_players,
    game_context,
  } = home;

  const featuredArticle =
    (lead_label
      ? articles.find((article) => article.primary_label === lead_label)
      : null) ??
    articles[0] ??
    null;

  const headline = lead_label
    ? `오늘 롯데 여론은 ${LABEL_HEADLINE[lead_label]} 중심입니다`
    : article_count > 0
      ? "오늘의 롯데 데스크 보드"
      : "다음 롯데 브리핑을 준비 중입니다";

  const subcopy =
    article_count > 0
      ? `오늘 ${article_count}건의 기사가 수집되었습니다. 주요 이슈, 선수 순위, 기사 피드 순으로 빠르게 스캔할 수 있습니다.`
      : "아직 수집된 기사가 없습니다. 파이프라인이 완료되면 히어로 카드와 순위가 자동으로 채워집니다.";

  const gameKicker = game_context
    ? `vs ${game_context.opponent} / ${game_context.home_away} / ${game_context.game_time ?? "TBD"}`
    : "SAJIK MATCHDAY BRIEFING";

  const playerRankingRows = top_players.slice(0, 5).map((mention) => ({
    id: String(mention.player.id),
    title: mention.player.name,
    meta: mention.player.position,
    value: String(mention.mention_count),
    href: `/players/${mention.player.id}`,
  }));

  const latestArticleRows = articles.slice(0, 5).map((article) => ({
    id: String(article.id),
    title: article.title,
    meta: `${article.source_name} / ${formatRelativeTime(article.published_at)}`,
    value: article.primary_label
      ? LABEL_META[article.primary_label].name
      : "Desk",
  }));

  return (
    <PageShell
      headerActions={[
        { href: "/players", label: "선수단" },
        { href: "/topics", label: "토픽" },
        { href: "/archive", label: "아카이브" },
      ]}
      seasonBadge="2026 KBO"
      footer={
        <p className="text-xs" style={{ color: "var(--dim)" }}>
          메타데이터 기반 팬 브리핑 서비스. 전체 맥락은 원문 기사를 확인하세요.
        </p>
      }
    >
      <HomeHeroDesk
        date={formatDateKo(today)}
        headline={headline}
        subcopy={subcopy}
        kicker={gameKicker}
        metaStat={
          article_count > 0
            ? { label: "stories", value: String(article_count) }
            : undefined
        }
      />

      <FanVoiceLayer contextType="home" contextId="today" />

      <section className="mb-10 grid gap-4 lg:grid-cols-[1.45fr_0.95fr]">
        <FeaturedArticleCard article={featuredArticle} />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <SignalCard
            title="수집 현황"
            eyebrow="오늘"
            value={String(article_count)}
            detail={
              lead_label
                ? `${label_counts[lead_label]}건 ${LABEL_META[lead_label].name}`
                : "분류된 기사 대기 중"
            }
            accent="red"
          />
          <SignalCard
            title="여론 스냅샷"
            eyebrow="스탠스"
            value={sentiment.analyzed > 0 ? `${sentiment.analyzed}` : "0"}
            detail="스탠스 데이터 보유 기사"
            accent="gold"
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
              <p
                className="mt-3 text-sm leading-7"
                style={{ color: "var(--muted)" }}
              >
                관련 뉴스 파이프라인이 완료되면 감정 막대가 표시됩니다.
              </p>
            )}
          </SignalCard>
        </div>
      </section>

      <section className="mb-10">
        <SectionHeader label="빠른 순위" accent="gold" />
        <div className="grid gap-4 xl:grid-cols-3">
          <RankingPanel
            eyebrow="선수 순위"
            title="최다 언급 선수"
            rows={playerRankingRows}
            accent="gold"
            emptyTitle="선수 순위가 비어있습니다"
            emptyBody="오늘의 기사-선수 연결이 완료되면 선수 언급 순위가 표시됩니다."
          />
          <RankingPanel
            eyebrow="데스크 보드"
            title="최신 헤드라인"
            rows={latestArticleRows}
            accent="red"
            emptyTitle="아직 헤드라인이 없습니다"
            emptyBody="수집이 완료되면 최신 기사 큐가 채워집니다."
          />
          <RankingPanel
            eyebrow="독자 순위"
            title="최다 조회 기사"
            rows={[]}
            accent="neutral"
            emptyTitle="백엔드 지원 필요"
            emptyBody="현재 API는 기사 조회수를 제공하지 않습니다. 조회수 지표 추가를 위한 백엔드 노트가 작성되었습니다."
          />
        </div>
      </section>

      {lead_label && lead_summary ? (
        <section className="mb-10">
          <SectionHeader label="주요 요약" accent="red" />
          <div
            className="rounded-[24px] p-6"
            style={{
              background: "rgba(255,255,255,0.72)",
              border: "1px solid var(--border)",
            }}
          >
            <p
              className="text-sm font-mono-code uppercase tracking-[0.18em]"
              style={{ color: "var(--red)" }}
            >
              {LABEL_META[lead_label].name}
            </p>
            <p
              className="mt-4 text-base leading-8"
              style={{ color: "var(--text)" }}
            >
              {lead_summary}
            </p>
          </div>
        </section>
      ) : null}

      <section>
        <SectionHeader label="전체 피드" />
        <ArticleFeed articles={articles} />
      </section>
    </PageShell>
  );
}
