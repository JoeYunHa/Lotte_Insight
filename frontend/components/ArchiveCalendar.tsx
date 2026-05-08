'use client'

// Client component: calendar month navigation + date selection.
// Receives all archive data from the server — no client-side fetch.

import { useState } from 'react'
import { LABEL_META } from '@/lib/label-config'
import type { TeamDailyReport } from '@/lib/types'

interface Props {
  reports: TeamDailyReport[]
  initialDate: string  // 'YYYY-MM-DD' — pre-selected on first render
}

const KO_DAYS = ['일', '월', '화', '수', '목', '금', '토']
const KO_MONTHS = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']

const RESULT_STYLE: Record<string, { bg: string; text: string }> = {
  '승': { bg: 'rgba(52,211,153,0.15)',  text: '#34d399' },
  '패': { bg: 'rgba(248,113,113,0.15)', text: '#f87171' },
  '무': { bg: 'rgba(148,163,184,0.15)', text: '#94a3b8' },
}

function getGameResult(report: TeamDailyReport): '승' | '패' | '무' | null {
  const summary = report.issue_summary
  if (summary.includes('승.') || summary.includes('승리') || summary.includes('완승') || summary.includes('역전승')) return '승'
  if (summary.includes('패.') || summary.includes('완패') || summary.includes('패배')) return '패'
  if (summary.includes('무.') || summary.includes('무승부')) return '무'
  return null
}

export function ArchiveCalendar({ reports, initialDate }: Props) {
  const initial = new Date(initialDate + 'T00:00:00')
  const [selectedDate, setSelectedDate] = useState(initialDate)
  const [viewYear, setViewYear] = useState(initial.getFullYear())
  const [viewMonth, setViewMonth] = useState(initial.getMonth())

  const reportMap = Object.fromEntries(reports.map(r => [r.date, r]))
  const selectedReport = reportMap[selectedDate]

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay()

  const cells: (number | null)[] = [
    ...Array<null>(firstDayOfWeek).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  const toDateStr = (day: number) =>
    `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }

  const sortedReports = [...reports].sort((a, b) => b.date.localeCompare(a.date))

  return (
    <div>
      {/* ── Calendar card ── */}
      <div
        className="rounded-lg p-4 mb-6"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        {/* Month nav */}
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={prevMonth}
            className="w-8 h-8 rounded flex items-center justify-center text-sm transition-colors hover:text-cream-100"
            style={{ color: 'var(--muted)', background: 'var(--surface-2)' }}
          >
            ‹
          </button>
          <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
            {viewYear}년 {KO_MONTHS[viewMonth]}
          </span>
          <button
            onClick={nextMonth}
            className="w-8 h-8 rounded flex items-center justify-center text-sm transition-colors hover:text-cream-100"
            style={{ color: 'var(--muted)', background: 'var(--surface-2)' }}
          >
            ›
          </button>
        </div>

        {/* Day labels */}
        <div className="grid grid-cols-7 mb-1">
          {KO_DAYS.map((d, i) => (
            <div
              key={d}
              className="text-center text-xs py-1 font-medium"
              style={{ color: i === 0 ? '#f87171' : i === 6 ? '#60a5fa' : 'var(--dim)' }}
            >
              {d}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="grid grid-cols-7 gap-0.5">
          {cells.map((day, idx) => {
            if (day === null) return <div key={`e-${idx}`} />
            const dateStr = toDateStr(day)
            const report = reportMap[dateStr]
            const isSelected = selectedDate === dateStr
            const result = report ? getGameResult(report) : null
            const dow = (firstDayOfWeek + day - 1) % 7

            return (
              <button
                key={dateStr}
                onClick={() => report && setSelectedDate(dateStr)}
                disabled={!report}
                className="relative aspect-square flex flex-col items-center justify-center rounded text-xs transition-all"
                style={{
                  background: isSelected ? 'var(--red)' : 'transparent',
                  color: isSelected
                    ? '#fff'
                    : dow === 0 ? '#f87171'
                    : dow === 6 ? '#60a5fa'
                    : report ? 'var(--text)' : 'var(--dim)',
                  cursor: report ? 'pointer' : 'default',
                  fontWeight: dateStr === initialDate ? '700' : '400',
                }}
              >
                {day}
                {report && !isSelected && (
                  <span
                    className="absolute bottom-1 w-1 h-1 rounded-full"
                    style={{ background: result ? RESULT_STYLE[result].text : 'var(--dim)' }}
                  />
                )}
              </button>
            )
          })}
        </div>

        {/* Legend */}
        <div
          className="flex items-center gap-4 mt-3 pt-3"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          {(['승', '패', '무'] as const).map(r => (
            <div key={r} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--muted)' }}>
              <span className="w-2 h-2 rounded-full" style={{ background: RESULT_STYLE[r].text }} />
              {r}
            </div>
          ))}
          <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--muted)' }}>
            <span className="w-2 h-2 rounded-full" style={{ background: 'var(--dim)' }} />
            休
          </div>
        </div>
      </div>

      {/* ── Selected report detail ── */}
      {selectedReport && (
        <div className="mb-8">
          <p className="text-xs mb-2" style={{ color: 'var(--dim)' }}>선택된 날짜</p>
          <ArchiveReportCard report={selectedReport} isSelected />
        </div>
      )}

      {/* ── Full list ── */}
      <div>
        <p className="text-xs mb-3" style={{ color: 'var(--dim)' }}>전체 기록</p>
        <div className="space-y-2.5">
          {sortedReports.map(report => (
            <button
              key={report.date}
              className="w-full text-left"
              onClick={() => setSelectedDate(report.date)}
            >
              <ArchiveReportCard report={report} isSelected={selectedDate === report.date} />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ArchiveReportCard({
  report,
  isSelected,
}: {
  report: TeamDailyReport
  isSelected: boolean
}) {
  const d = new Date(report.date + 'T00:00:00')
  const label = `${d.getMonth() + 1}월 ${d.getDate()}일 ${KO_DAYS[d.getDay()]}요일`
  const result = getGameResult(report)

  return (
    <div
      className="rounded-lg p-4 transition-all"
      style={{
        background: isSelected ? 'var(--surface-2)' : 'var(--surface)',
        border: `1px solid ${isSelected ? 'var(--red)' : 'var(--border)'}`,
      }}
    >
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
            {label}
          </span>
          {result && (
            <span
              className="text-xs font-mono-code font-bold px-2 py-0.5 rounded"
              style={{ background: RESULT_STYLE[result].bg, color: RESULT_STYLE[result].text }}
            >
              {result}
            </span>
          )}
        </div>
        <span className="text-xs font-mono-code" style={{ color: 'var(--muted)' }}>
          <span style={{ color: 'var(--dim)' }}>기사 </span>
          {report.article_count}
        </span>
      </div>
      <p className="text-xs leading-relaxed mb-2.5" style={{ color: 'var(--muted)' }}>
        {report.issue_summary}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {report.top_labels.map(label => (
          <span
            key={label}
            className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded"
            style={{ background: 'var(--bg)', color: 'var(--dim)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: LABEL_META[label].dot }} />
            {LABEL_META[label].name}
          </span>
        ))}
      </div>
    </div>
  )
}
