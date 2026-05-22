import { ArchiveCalendar } from '@/components/ArchiveCalendar'
import { PageIntro } from '@/components/PageIntro'
import { PageShell } from '@/components/PageShell'
import { getTeamReports } from '@/lib/api'
import { getTodayKST } from '@/lib/time'
import type { TeamDailyReport } from '@/lib/types'

export const dynamic = 'force-dynamic'

export default async function ArchivePage() {
  const today = getTodayKST()
  let reports: TeamDailyReport[] = []
  try {
    reports = await getTeamReports(60)
  } catch {
    reports = []
  }

  return (
    <PageShell headerActions={[{ href: '/', label: 'Today' }]}>
      <PageIntro title="Archive" />

      {reports.length === 0 ? (
        <p className="text-sm py-16 text-center" style={{ color: 'var(--dim)' }}>
          No reports are available yet.
        </p>
      ) : (
        <ArchiveCalendar reports={reports} initialDate={today} />
      )}
    </PageShell>
  )
}
