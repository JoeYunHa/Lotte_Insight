import Link from 'next/link'

interface RankingRow {
  id: string
  title: string
  meta?: string
  value: string
  href?: string
}

interface RankingPanelProps {
  title: string
  eyebrow: string
  rows: RankingRow[]
  accent?: 'navy' | 'red' | 'blue'
  emptyTitle?: string
  emptyBody?: string
}

export function RankingPanel({
  title,
  eyebrow,
  rows,
  accent = 'blue',
  emptyTitle = '순위 데이터가 없습니다',
  emptyBody = '관련 데이터가 준비되면 이 영역에 순위가 표시됩니다.',
}: RankingPanelProps) {
  const theme =
    accent === 'navy'
      ? {
          shell: 'linear-gradient(180deg, rgba(var(--lotte-navy-rgb), 0.94) 0%, rgba(var(--lotte-navy-rgb), 0.9) 100%)',
          panel: 'rgba(var(--lotte-white-rgb), 0.08)',
          hero: 'linear-gradient(135deg, rgba(var(--lotte-white-rgb), 0.12) 0%, rgba(var(--lotte-blue-rgb), 0.22) 100%)',
          row: 'rgba(var(--lotte-white-rgb), 0.08)',
          badge: 'rgba(var(--lotte-white-rgb), 0.14)',
          border: 'rgba(var(--lotte-blue-rgb), 0.22)',
          accent: 'var(--lotte-navy)',
          title: 'var(--lotte-navy)',
          meta: 'rgba(var(--lotte-navy-rgb), 0.74)',
        }
      : accent === 'red'
        ? {
            shell: 'linear-gradient(180deg, rgba(var(--lotte-red-rgb), 0.12) 0%, rgba(var(--lotte-cream-rgb), 0.98) 100%)',
            panel: 'rgba(var(--lotte-white-rgb), 0.72)',
            hero: 'linear-gradient(135deg, rgba(var(--lotte-red-rgb), 0.18) 0%, rgba(var(--lotte-cream-deep-rgb), 0.98) 100%)',
            row: 'rgba(var(--lotte-white-rgb), 0.72)',
            badge: 'rgba(var(--lotte-red-rgb), 0.12)',
            border: 'var(--red-border)',
            accent: 'var(--red)',
            title: 'var(--text)',
            meta: 'var(--dim)',
          }
        : {
            shell: 'linear-gradient(180deg, rgba(var(--lotte-blue-rgb), 0.16) 0%, rgba(var(--lotte-cream-rgb), 0.98) 100%)',
            panel: 'rgba(var(--lotte-white-rgb), 0.74)',
            hero: 'linear-gradient(135deg, rgba(var(--lotte-blue-rgb), 0.2) 0%, rgba(var(--lotte-cream-deep-rgb), 0.98) 100%)',
            row: 'rgba(var(--lotte-white-rgb), 0.72)',
            badge: 'rgba(var(--lotte-blue-rgb), 0.14)',
            border: 'var(--blue-border)',
            accent: 'var(--blue)',
            title: 'var(--text)',
            meta: 'var(--dim)',
          }

  return (
    <section
      className="overflow-hidden rounded-[26px]"
      style={{
        background: theme.shell,
        border: `1px solid ${theme.border}`,
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <div className="p-5 md:p-6">
        <div
          className="rounded-[22px] px-4 py-4"
          style={{
            background: theme.panel,
            border: `1px solid ${theme.border}`,
          }}
        >
          <p
            className="inline-flex rounded-full px-2.5 py-1 text-[11px] font-mono-code uppercase tracking-[0.2em]"
            style={{ color: theme.accent, background: theme.badge }}
          >
            {eyebrow}
          </p>
          <h3 className="mt-3 text-xl font-serif-kr font-bold" style={{ color: theme.title }}>
            {title}
          </h3>
        </div>

        {rows.length === 0 ? (
          <div
            className="mt-4 rounded-[22px] p-4"
            style={{ background: theme.panel, border: `1px solid ${theme.border}` }}
          >
            <p className="text-sm font-semibold" style={{ color: theme.title }}>
              {emptyTitle}
            </p>
            <p className="mt-2 text-sm leading-7" style={{ color: theme.meta }}>
              {emptyBody}
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {rows.map((row, index) => {
              const isTop = index === 0
              const content = (
                <div
                  className="grid grid-cols-[56px_1fr_auto] items-start gap-4 rounded-[22px] p-4 transition-colors"
                  style={{
                    background: isTop ? theme.hero : theme.row,
                    border: `1px solid ${isTop ? theme.border : 'var(--border)'}`,
                  }}
                >
                  <div
                    className="flex h-14 w-14 items-center justify-center rounded-[18px] text-base font-mono-code font-bold"
                    style={{
                      background: isTop ? theme.badge : 'rgba(var(--lotte-navy-rgb), 0.06)',
                      color: isTop ? theme.accent : theme.meta,
                    }}
                  >
                    {String(index + 1).padStart(2, '0')}
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm font-semibold leading-6" style={{ color: theme.title }}>
                      {row.title}
                    </p>
                    {row.meta ? (
                      <p className="mt-2 truncate text-xs" style={{ color: theme.meta }}>
                        {row.meta}
                      </p>
                    ) : null}
                  </div>
                  <div
                    className="rounded-[18px] px-3 py-2 text-right"
                    style={{
                      background: isTop ? theme.badge : 'rgba(var(--lotte-white-rgb), 0.46)',
                    }}
                  >
                    <p className="text-lg font-mono-code font-bold" style={{ color: theme.accent }}>
                      {row.value}
                    </p>
                  </div>
                </div>
              )

              return row.href ? (
                <Link key={row.id} href={row.href} className="block">
                  {content}
                </Link>
              ) : (
                <div key={row.id}>{content}</div>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
