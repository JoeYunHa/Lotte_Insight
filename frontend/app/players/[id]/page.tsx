import { notFound } from "next/navigation";
import { ArticleCard } from "@/components/ArticleCard";
import { FanVoiceLayer } from "@/components/FanVoice/FanVoiceLayer";
import { PageShell } from "@/components/Page/PageShell";
import {
  PlayerIdentityHeader,
  PlayerStatsCard,
} from "@/components/Player/PlayerStatsCard";
import { getArticles, getPlayer, getPlayerReport } from "@/lib/api";
import { withFallback, withResult } from "@/lib/server-data";
import type { Article, PlayerDailyReport } from "@/lib/types";
import { getTodayKST } from "@/lib/time";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PlayerPage({ params }: Props) {
  const { id } = await params;
  const today = getTodayKST();

  const playerResult = await withResult(
    () => getPlayer(id, today),
    `players[id]:getPlayer:${id}`,
  );
  if (!playerResult.ok) {
    notFound();
  }
  const player = playerResult.data;
  if (!player) notFound();

  // Optional sections should never force a 404.
  const [report, playerArticles] = await Promise.all([
    withFallback(
      () => getPlayerReport(id, today),
      null as PlayerDailyReport | null,
      `players[id]:getPlayerReport:${id}`,
    ),
    withFallback(
      () => getArticles({ player_id: id, limit: 10 }),
      [] as Article[],
      `players[id]:getArticles:${id}`,
    ),
  ]);

  const stats = player.stats?.[0] ?? null;

  return (
    <PageShell
      headerActions={[
        { href: "/players", label: "선수단" },
        { href: "/", label: "오늘" },
      ]}
    >
      <PlayerIdentityHeader
        playerName={player.name}
        playerNumber={player.number}
        playerPosition={player.position}
        playerStatus={player.status}
      />

      <FanVoiceLayer contextType="player" contextId={id} />

      <PlayerStatsCard stats={stats} statsDate={today} />

      <div className="mb-8">
        <p className="text-xs mb-2" style={{ color: "var(--dim)" }}>
          오늘의 선수 리포트
        </p>
        <div
          className="rounded-lg p-4"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderLeft: "3px solid var(--red)",
          }}
        >
          {report ? (
            <p
              className="text-sm leading-relaxed"
              style={{ color: "var(--muted)" }}
            >
              {report.insight}
            </p>
          ) : (
            <p className="text-sm" style={{ color: "var(--dim)" }}>
              이 날짜의 리포트가 아직 생성되지 않았습니다.
            </p>
          )}
        </div>
      </div>

      <div>
        <p className="text-xs mb-3" style={{ color: "var(--dim)" }}>
          최근 기사 ({playerArticles.length})
        </p>
        {playerArticles.length > 0 ? (
          <div className="space-y-2.5">
            {playerArticles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                variant="compact"
                showKeyPlayers={false}
              />
            ))}
          </div>
        ) : (
          <p
            className="text-sm py-8 text-center"
            style={{ color: "var(--dim)" }}
          >
            최근 기사가 없습니다.
          </p>
        )}
      </div>
    </PageShell>
  );
}
