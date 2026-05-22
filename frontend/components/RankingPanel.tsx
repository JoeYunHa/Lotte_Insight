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
  accent?: 'gold' | 'red' | 'neutral'
  emptyTitle?: string
  emptyBody?: string
}

export function RankingPanel({
  title,
  eyebrow,
  rows,
  accent = 'neutral',
  emptyTitle = 'No ranking data',
  emptyBody = 'This block is ready and waiting for backend support.',
}: RankingPanelProps) {
  const accentColor =
    accent === 'gold' ? 'var(--gold)' :
    accent === 'red' ? 'var(--red)' :
    'var(--border-strong)'

  return (
    <section
      className="rounded-[24px] p-5 md:p-6"
      style={{
        background: 'linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(241,232,218,0.98) 100%)',
        border: `1px solid ${accentColor === 'var(--border-strong)' ? 'var(--border)' : 'rgba(225,6,44,0.14)'}`,
      }}
    >
      <p className="text-[11px] font-mono-code uppercase tracking-[0.22em]" style={{ color: accentColor }}>
        {eyebrow}
      </p>
      <h3 className="mt-3 text-xl font-serif-kr font-bold" style={{ color: 'var(--text)' }}>
        {title}
      </h3>

      {rows.length === 0 ? (
        <div
          className="mt-5 rounded-[20px] p-4"
          style={{ background: 'rgba(255,255,255,0.65)', border: '1px dashed var(--border)' }}
        >
          <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
            {emptyTitle}
          </p>
          <p className="mt-2 text-sm leading-7" style={{ color: 'var(--muted)' }}>
            {emptyBody}
          </p>
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {rows.map((row, index) => {
            const content = (
              <div
                className="flex items-start gap-4 rounded-[20px] px-4 py-3 transition-colors"
                style={{
                  background: index === 0 ? 'rgba(255,255,255,0.82)' : 'rgba(255,255,255,0.58)',
                  border: '1px solid var(--border)',
                }}
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-mono-code font-bold"
                  style={{
                    background: index === 0 ? 'rgba(225,6,44,0.12)' : 'var(--surface-2)',
                    color: index === 0 ? 'var(--text)' : 'var(--muted)',
                  }}
                >
                  {String(index + 1).padStart(2, '0')}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-6" style={{ color: 'var(--text)' }}>
                    {row.title}
                  </p>
                  {row.meta ? (
                    <p className="mt-1 text-xs" style={{ color: 'var(--dim)' }}>
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
