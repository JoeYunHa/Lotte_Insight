// Server Component — fetches player + report + articles in parallel.

import { notFound } from 'next/navigation'
import Link from 'next/link'
import { LabelBadge, StanceBadge } from '@/components/Badges'
import { LABEL_META } from '@/lib/label-config'
import { getPlayer, getPlayerReport, getPlayerStats, getArticles } from '@/lib/api'
import { formatRelativeTime, formatDate, getTodayKST } from '@/lib/time'
import type { Article } from '@/lib/types'

interface Props {
  params: { id: string }
}

export default async function PlayerPage({ params }: Props) {
  const today = getTodayKST()

  const [player, report, stats, allArticles] = await Promise.all([
    getPlayer(params.id),
    getPlayerReport(params.id, today),
    getPlayerStats(params.id, today),
    getArticles({}),
  ])

  if (!player) notFound()

  // Filter articles that mention this player.
  // When the real API is wired up, pass player_id to getArticles() instead.
  const playerArticles = allArticles
    .filter(a => a.key_players?.includes(player.name))
    .slice(0, 10)

  const isHitter = stats?.avg != null || stats?.ops != null

  const statusColor = player.status === '1군'
    ? { bg: 'rgba(52,211,153,0.12)', text: '#34d399', border: 'rgba(52,211,153,0.25)' }
    : player.status === '말소'
    ? { bg: 'rgba(248,113,113,0.12)', text: '#f87171', border: 'rgba(248,113,113,0.25)' }
    : { bg: 'rgba(148,163,184,0.12)', text: '#94a3b8', border: 'rgba(148,163,184,0.25)' }

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
          <Link
            href="/"
            className="text-sm transition-colors hover:text-cream-100"
            style={{ color: 'var(--muted)' }}
          >
            ← 오늘의 리포트
          </Link>
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
              style={{ background: 'var(--red)', color: '#fff' }}
            >
              L
            </div>
            <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>롯데 인사이트</span>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 pb-20">

        {/* ── Player header ── */}
        <div className="pt-10 pb-6">
          <div className="flex items-center gap-2 mb-1">
            {player.number && (
              <span
                className="text-xs font-mono-code px-2 py-0.5 rounded"
                style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
              >
                #{player.number}
              </span>
            )}
            <span className="text-xs" style={{ color: 'var(--muted)' }}>{player.position}</span>
            <span
              className="text-xs px-2 py-0.5 rounded"
              style={{ background: statusColor.bg, color: statusColor.text, border: `1px solid ${statusColor.border}` }}
            >
              {player.status}
            </span>
          </div>
          <h1 className="font-serif-kr text-3xl font-black my-2" style={{ color: 'var(--text)' }}>
            {player.name}
          </h1>
          <div className="h-px w-full mt-4" style={{ background: 'var(--border)' }} />
        </div>

        {/* ── Stats card ── */}
        {stats ? (
          <div
            className="rounded-lg p-4 mb-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <p className="text-xs mb-3" style={{ color: 'var(--dim)' }}>
              시즌 기록 · {formatDate(today)}
            </p>
            <div className="flex gap-6 flex-wrap">
              {isHitter ? (
                <>
                  {stats.avg != null && <StatItem label="타율" value={stats.avg.toFixed(3)} />}
                  {stats.ops != null && <StatItem label="OPS" value={stats.ops.toFixed(3)} />}
                  {(stats.raw_stats as Record<string, unknown>).rbi != null && (
                    <StatItem label="타점" value={String((stats.raw_stats as Record<string, unknown>).rbi)} />
                  )}
                </>
              ) : (
                <>
                  {stats.era != null && <StatItem label="ERA" value={stats.era.toFixed(2)} />}
                  {(stats.raw_stats as Record<string, unknown>).sv != null && (
                    <StatItem label="세이브" value={String((stats.raw_stats as Record<string, unknown>).sv)} />
                  )}
                  {(stats.raw_stats as Record<string, unknown>).k != null && (
                    <StatItem label="탈삼진" value={String((stats.raw_stats as Record<string, unknown>).k)} />
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <div
            className="rounded-lg p-4 mb-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <p className="text-xs" style={{ color: 'var(--dim)' }}>기록 데이터 없음</p>
          </div>
        )}

        {/* ── Daily report (GPT-4o mini output) ── */}
        <div className="mb-8">
          <p className="text-xs mb-2" style={{ color: 'var(--dim)' }}>오늘의 리포트</p>
          <div
            className="rounded-lg p-4"
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderLeft: '3px solid var(--red)',
            }}
          >
            {report ? (
              <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                {report.insight}
              </p>
            ) : (
              <p className="text-sm" style={{ color: 'var(--dim)' }}>
                오늘의 리포트가 아직 생성되지 않았습니다.
              </p>
            )}
          </div>
        </div>

        {/* ── Recent articles ── */}
        <div>
          <p className="text-xs mb-3" style={{ color: 'var(--dim)' }}>
            최근 기사 ({playerArticles.length}건)
          </p>
          {playerArticles.length > 0 ? (
            <div className="space-y-2.5">
              {playerArticles.map(article => (
                <PlayerArticleRow key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <p className="text-sm py-8 text-center" style={{ color: 'var(--dim)' }}>
              최근 7일 기사가 없습니다
            </p>
          )}
        </div>

      </main>
    </div>
  )
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>{label}</p>
      <p className="font-mono-code text-2xl font-bold" style={{ color: 'var(--text)' }}>{value}</p>
    </div>
  )
}

function PlayerArticleRow({ article }: { article: Article }) {
  const dot = article.primary_label ? LABEL_META[article.primary_label].dot : 'var(--dim)'
  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${dot}`,
      }}
    >
      <div className="pl-4 pr-4 pt-3 pb-3">
        <div className="flex items-center gap-2 mb-1.5">
          {article.primary_label && <LabelBadge label={article.primary_label} />}
          {article.lotte_stance && <StanceBadge stance={article.lotte_stance} />}
        </div>
        <p className="text-sm font-semibold leading-snug mb-1" style={{ color: 'var(--text)' }}>
          {article.title}
        </p>
        {article.event_summary && (
          <p className="text-xs leading-relaxed mb-2" style={{ color: 'var(--muted)' }}>
            {article.event_summary}
          </p>
        )}
        <div className="flex items-center justify-between">
          <span className="text-xs" style={{ color: 'var(--dim)' }}>
            {article.source_name} · {formatRelativeTime(article.published_at)}
          </span>
          <a
            href={article.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs transition-colors hover:text-lotte-red"
            style={{ color: 'var(--muted)' }}
          >
            원문 →
          </a>
        </div>
      </div>
    </div>
  )
}
