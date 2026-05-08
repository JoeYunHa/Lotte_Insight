// Server Component — fetches all archive data then hands off to Client calendar.

import Link from 'next/link'
import { ArchiveCalendar } from '@/components/ArchiveCalendar'
import { getTeamReports } from '@/lib/api'
import { getTodayKST } from '@/lib/time'

export default async function ArchivePage() {
  const today = getTodayKST()
  // Fetch up to 60 days of past reports — enough for the current + previous month.
  const reports = await getTeamReports(60)

  return (
    <div className="min-h-dvh" style={{ background: 'var(--bg)' }}>

      {/* ── Top accent bar ── */}
      <div className="h-[3px] w-full" style={{ background: 'var(--red)' }} />

      {/* ── Header ── */}
      <header
        className="sticky top-0 z-50 backdrop-blur-md"
        style={{ background: 'rgba(0, 18, 40, 0.92)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-7 h-7 rounded flex items-center justify-center text-sm font-bold"
              style={{ background: 'var(--red)', color: '#fff' }}
            >
              L
            </div>
            <span className="font-semibold text-sm tracking-wide" style={{ color: 'var(--text)' }}>
              롯데 인사이트
            </span>
          </div>
          <Link href="/" className="text-xs transition-colors hover:text-cream-100" style={{ color: 'var(--muted)' }}>
            오늘로 →
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 pb-20">

        {/* ── Title ── */}
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
            아직 저장된 리포트가 없습니다.
          </p>
        ) : (
          /* Client Component handles calendar navigation and date selection */
          <ArchiveCalendar reports={reports} initialDate={today} />
        )}

      </main>
    </div>
  )
}
