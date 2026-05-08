// Server Component — fetches data at request time (or from ISR cache).
// All data-fetching happens here; child Client components receive data as props.

import Link from 'next/link'
import { ArticleFeed } from '@/components/ArticleFeed'
import { LabelBadge } from '@/components/Badges'
import {
  getTeamReport,
  getArticles,
  getTopMentionedPlayers,
  computeLabelCounts,
} from '@/lib/api'
import { formatDateKo, getTodayKST } from '@/lib/time'
import { ALL_LABELS } from '@/lib/label-config'

export default async function HomePage() {
  const today = getTodayKST()

  // Parallel fetch — when real API is wired up these will be concurrent HTTP calls.
  const [report, articles, topPlayers] = await Promise.all([
    getTeamReport(today),
    getArticles({ date: today }),
    getTopMentionedPlayers(today),
  ])

  const labelCounts = computeLabelCounts(articles)

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
            <span
              className="text-xs px-1.5 py-0.5 rounded font-mono-code"
              style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
            >
              2026 KBO
            </span>
          </div>
          <nav className="flex items-center gap-4">
            <Link href="/archive" className="text-xs transition-colors hover:text-cream-100" style={{ color: 'var(--muted)' }}>
              아카이브
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 pb-20">

        {/* ── Date + headline ── */}
        <div className="pt-10 pb-6">
          <p className="text-xs font-medium mb-3 font-mono-code" style={{ color: 'var(--muted)' }}>
            {formatDateKo(today)}
          </p>
          <h1 className="font-serif-kr text-3xl font-black leading-tight mb-4" style={{ color: 'var(--text)' }}>
            오늘의 롯데
          </h1>
          <div className="h-px w-full mb-4" style={{ background: 'var(--border)' }} />
          {report ? (
            <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
              {report.issue_summary}
            </p>
          ) : (
            <p className="text-sm" style={{ color: 'var(--dim)' }}>
              오늘의 리포트가 아직 생성되지 않았습니다.
            </p>
          )}
        </div>

        {/* ── Stats strip ── */}
        <div
          className="rounded-lg p-4 mb-4"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>오늘 수집 기사</span>
            <span className="font-mono-code text-lg font-bold" style={{ color: 'var(--text)' }}>
              {articles.length}
            </span>
            <span className="text-xs" style={{ color: 'var(--dim)' }}>건</span>
          </div>
          {articles.length > 0 ? (
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {ALL_LABELS
                .filter(l => labelCounts[l] > 0)
                .map(l => (
                  <div key={l} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--muted)' }}>
                    <LabelBadge label={l} />
                    <span className="font-mono-code" style={{ color: 'var(--text)' }}>{labelCounts[l]}</span>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-xs" style={{ color: 'var(--dim)' }}>수집된 기사가 없습니다</p>
          )}
        </div>

        {/* ── Top mentioned players ── */}
        {topPlayers.length > 0 && (
          <div className="mb-8">
            <p className="text-xs mb-2.5" style={{ color: 'var(--dim)' }}>주요 언급 선수</p>
            <div className="flex flex-wrap gap-2">
              {topPlayers.map(({ player, mention_count }) => (
                <Link
                  key={player.id}
                  href={`/players/${player.id}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-sm transition-all hover:-translate-y-px"
                  style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
                >
                  {player.name}
                  <span className="font-mono-code text-xs" style={{ color: 'var(--gold)' }}>
                    ×{mention_count}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* ── Article feed (Client Component for filter state) ── */}
        <ArticleFeed articles={articles} />

      </main>

      <footer className="text-center pb-8">
        <p className="text-xs" style={{ color: 'var(--dim)' }}>
          롯데 인사이트 · 뉴스 원문은 각 출처를 통해 확인하세요
        </p>
      </footer>
    </div>
  )
}
