import { ArchiveCalendar } from '@/components/ArchiveCalendar'
import { PageShell } from '@/components/PageShell'
import { getTeamReports } from '@/lib/api'
import { getTodayKST } from '@/lib/time'

export const revalidate = 3600

export default async function ArchivePage() {
  const today = getTodayKST()
  const reports = await getTeamReports(60)

  return (
    <PageShell headerAction={{ href: '/', label: '오늘로' }}>
      <div className="pt-10 pb-6">
        <p className="text-xs font-medium mb-3 font-mono-code" style={{ color: 'var(--muted)' }}>
          2026 KBO 시즌
        </p>
        <h1 className="font-serif-kr text-3xl font-black leading-tight mb-4" style={{ color: 'var(--text)' }}>
          시즌 아카이브
        </h1>
        <div className="h-px w-full" style={{ background: 'var(--border)' }} />
      </div>

      {reports.length === 0 ? (
        <p className="text-sm py-16 text-center" style={{ color: 'var(--dim)' }}>
          아직 등록된 리포트가 없습니다.
        </p>
      ) : (
        <ArchiveCalendar reports={reports} initialDate={today} />
      )}
    </PageShell>
  )
}
