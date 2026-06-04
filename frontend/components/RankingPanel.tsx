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
  emptyTitle = '?쒖쐞 ?곗씠???놁쓬',
  emptyBody = '諛깆뿏??吏?먯쓣 湲곕떎由ш퀬 ?덉뒿?덈떎.',
}: RankingPanelProps) {
  const accentColor =
    accent === 'navy' ? 'var(--text)' :
    accent === 'red' ? 'var(--red)' :
    'var(--blue)'
  const borderColor =
    accent === 'navy' ? 'var(--navy-border)' :
    accent === 'red' ? 'var(--red-border)' :
    'var(--blue-border)'
  const panelBackground =
    accent === 'navy'
      ? 'linear-gradient(180deg, rgba(var(--lotte-navy-rgb), 0.94) 0%, rgba(var(--lotte-navy-rgb), 0.88) 16%, rgba(var(--lotte-cream-rgb), 0.98) 16%, rgba(var(--lotte-white-rgb), 0.9) 100%)'
      : accent === 'red'
        ? 'linear-gradient(180deg, rgba(var(--lotte-red-rgb), 0.12) 0%, rgba(var(--lotte-cream-rgb), 0.98) 22%, rgba(var(--lotte-white-rgb), 0.9) 100%)'
        : 'linear-gradient(180deg, rgba(var(--lotte-blue-rgb), 0.16) 0%, rgba(var(--lotte-cream-rgb), 0.98) 22%, rgba(var(--lotte-white-rgb), 0.9) 100%)'
  const headerTextColor = accent === 'navy' ? 'var(--text-on-accent)' : 'var(--text)'
  const eyebrowColor = accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.8)' : accentColor
  const subtleTextColor = accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.74)' : 'var(--muted)'

  return (
    <section
      className="rounded-[24px] p-5 md:p-6"
      style={{
        background: panelBackground,
        border: `1px solid ${borderColor}`,
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <p className="text-[11px] font-mono-code uppercase tracking-[0.22em]" style={{ color: eyebrowColor }}>
        {eyebrow}
      </p>
      <h3 className="mt-3 text-xl font-serif-kr font-bold" style={{ color: headerTextColor }}>
        {title}
      </h3>

      {rows.length === 0 ? (
        <div
          className="mt-5 rounded-[20px] p-4"
          style={{
            background: accent === 'navy' ? 'rgba(var(--lotte-white-rgb), 0.08)' : 'var(--surface-glass-muted)',
            border: `1px dashed ${borderColor}`,
          }}
        >
          <p className="text-sm font-semibold" style={{ color: headerTextColor }}>
            {emptyTitle}
          </p>
          <p className="mt-2 text-sm leading-7" style={{ color: subtleTextColor }}>
            {emptyBody}
          </p>
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {rows.map((row, index) => {
            const isTop = index === 0
            const content = (
              <div
                className="flex items-start gap-4 rounded-[20px] px-4 py-3 transition-colors"
                style={{
                  background: isTop
                    ? accent === 'navy'
                      ? 'linear-gradient(135deg, rgba(var(--lotte-white-rgb), 0.16) 0%, rgba(var(--lotte-blue-rgb), 0.22) 100%)'
                      : 'linear-gradient(135deg, rgba(var(--lotte-cream-deep-rgb), 0.98) 0%, rgba(var(--lotte-blue-rgb), 0.12) 100%)'
                    : accent === 'navy'
                      ? 'rgba(var(--lotte-white-rgb), 0.08)'
                      : 'var(--surface-glass-muted)',
                  border: isTop ? `1px solid ${borderColor}` : '1px solid var(--border)',
                }}
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-mono-code font-bold"
                  style={{
                    background: isTop
                      ? accent === 'red'
                        ? 'var(--red-soft-strong)'
                        : accent === 'navy'
                          ? 'rgba(var(--lotte-white-rgb), 0.16)'
                          : 'var(--blue-soft-strong)'
                      : accent === 'navy'
                        ? 'rgba(var(--lotte-white-rgb), 0.12)'
                        : 'var(--surface-2)',
                    color: isTop ? accentColor : accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.84)' : 'var(--muted)',
                  }}
                >
                  {String(index + 1).padStart(2, '0')}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm font-semibold leading-6" style={{ color: accent === 'navy' ? 'var(--text-on-accent)' : 'var(--text)' }}>
                    {row.title}
                  </p>
                  {row.meta ? (
                    <p className="mt-1 truncate text-xs" style={{ color: accent === 'navy' ? 'rgba(var(--lotte-cream-rgb), 0.72)' : 'var(--dim)' }}>
                      {row.meta}
                    </p>
                  ) : null}
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-lg font-mono-code font-bold" style={{ color: accentColor }}>
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
    </section>
  )
}
