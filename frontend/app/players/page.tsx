import Link from "next/link";
import { FanVoiceLayer } from "@/components/FanVoice/FanVoiceLayer";
import { PageIntro } from "@/components/Page/PageIntro";
import { PageShell } from "@/components/Page/PageShell";
import { SectionHeader } from "@/components/SectionHeader";
import { getPlayers } from "@/lib/api";
import {
  classifyPosition,
  groupPlayers,
  POSITION_GROUPS,
} from "@/lib/player/player-position";
import {
  isActiveStatus,
  PLAYER_STATUS_META,
  toKnownPlayerStatus,
} from "@/lib/player/player-status";
import type { Player } from "@/lib/types";

export const dynamic = "force-dynamic";

function PlayerCard({ player }: { player: Player }) {
  const knownStatus = toKnownPlayerStatus(player.status);
  const statusMeta = PLAYER_STATUS_META[knownStatus];
  const isActive = isActiveStatus(player.status);

  return (
    <Link
      href={`/players/${player.id}`}
      className="block rounded-lg p-3.5 transition-all duration-200 group"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        opacity: isActive ? 1 : 0.55,
      }}
    >
      <div className="flex items-center gap-3">
        <span
          className="text-lg font-bold font-mono-code leading-none w-8 shrink-0 text-center"
          style={{ color: isActive ? "var(--gold)" : "var(--dim)" }}
        >
          {player.number ?? "--"}
        </span>

        <div className="flex-1 min-w-0">
          <p
            className="font-bold text-sm leading-tight transition-colors group-hover:text-lotte-red truncate"
            style={{ color: "var(--text)" }}
          >
            {player.name}
          </p>
          <p
            className="text-xs mt-0.5 truncate"
            style={{ color: "var(--dim)" }}
          >
            {player.position}
          </p>
        </div>

        <span
          className="text-[10px] font-mono-code font-bold shrink-0"
          style={{ color: statusMeta.color }}
        >
          {statusMeta.label}
        </span>
      </div>
    </Link>
  );
}

export default async function PlayersPage() {
  let players: Player[] = [];
  try {
    players = await getPlayers();
  } catch {
    players = [];
  }

  const groups = groupPlayers(players);
  const activeCount = players.filter((player) =>
    isActiveStatus(player.status),
  ).length;

  return (
    <PageShell
      headerActions={[
        { href: "/", label: "오늘" },
        { href: "/archive", label: "아카이브" },
      ]}
    >
      <PageIntro
        title="롯데 선수단"
        subtitle={`활성 ${activeCount} / 전체 ${players.length}`}
      />

      <FanVoiceLayer contextType="home" contextId="players" />

      {players.length === 0 ? (
        <p
          className="text-sm py-16 text-center"
          style={{ color: "var(--dim)" }}
        >
          선수 데이터가 없습니다.
        </p>
      ) : (
        POSITION_GROUPS.map((group) => {
          const list = groups[group.key];
          if (list.length === 0) return null;
          const sorted = [...list].sort((a, b) => {
            if (isActiveStatus(a.status) && !isActiveStatus(b.status))
              return -1;
            if (!isActiveStatus(a.status) && isActiveStatus(b.status)) return 1;
            const aNo = Number(a.number) || 999;
            const bNo = Number(b.number) || 999;
            return aNo - bNo;
          });
          return (
            <section key={group.key} className="mb-10">
              <SectionHeader label={group.label} />
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {sorted.map((player) => (
                  <PlayerCard key={player.id} player={player} />
                ))}
              </div>
            </section>
          );
        })
      )}

      {groups.etc.length > 0 ? (
        <section className="mb-10">
          <SectionHeader label="기타" />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {groups.etc.map((player) => (
              <PlayerCard key={player.id} player={player} />
            ))}
          </div>
        </section>
      ) : null}
    </PageShell>
  );
}
