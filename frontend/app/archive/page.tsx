import { ArchiveCalendar } from "@/components/ArchiveCalendar";
import { FanVoiceLayer } from "@/components/FanVoice/FanVoiceLayer";
import { PageIntro } from "@/components/Page/PageIntro";
import { PageShell } from "@/components/Page/PageShell";
import { getTeamReports } from "@/lib/api";
import { withFallback } from "@/lib/server-data";
import { getTodayKST } from "@/lib/time";

export const dynamic = "force-dynamic";

export default async function ArchivePage() {
  const today = getTodayKST();
  const reports = await withFallback(() => getTeamReports(60), [], "archive:getTeamReports");

  return (
    <PageShell headerActions={[{ href: "/", label: "오늘" }]}>
      <PageIntro title="아카이브" />

      <FanVoiceLayer contextType="home" contextId="archive" />

      {reports.length === 0 ? (
        <p
          className="text-sm py-16 text-center"
          style={{ color: "var(--dim)" }}
        >
          아직 리포트가 없습니다.
        </p>
      ) : (
        <ArchiveCalendar reports={reports} initialDate={today} />
      )}
    </PageShell>
  );
}
