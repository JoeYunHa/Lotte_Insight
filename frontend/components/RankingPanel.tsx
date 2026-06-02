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
  emptyTitle = '순위 데이터 없음',
  emptyBody = '백엔드 지원을 기다리고 있습니다.',
}: RankingPanelProps) {
  const accentColor =
    accent === 'gold' ? 'var(--gold)' :
    accent === 'red' ? 'var(--red)' :
    'var(--border-strong)'

  return (
    <section
      className="rounded-[24px] p-5 md:p-6"
      style={{
        background: 'var(--gradient-surface)',
        border: `1px solid ${accentColor === 'var(--border-strong)' ? 'var(--border)' : 'var(--red-soft-strong)'}`,
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
          style={{ background: 'var(--surface-glass-muted)', border: '1px dashed var(--border)' }}
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
            const isTop = index === 0
            const content = (
              <div
                className="flex items-start gap-4 rounded-[20px] px-4 py-3 transition-colors"
                style={{
                  background: isTop
                    ? 'linear-gradient(135deg, rgba(var(--lotte-navy-rgb), 0.1) 0%, rgba(var(--lotte-white-rgb), 0.92) 100%)'
                    : 'var(--surface-glass-muted)',
                  border: isTop ? '1px solid var(--gold-border)' : '1px solid var(--border)',
                }}
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-mono-code font-bold"
                  style={{
                    background: isTop ? 'var(--gold-soft-strong)' : 'var(--surface-2)',
                    color: isTop ? 'var(--gold)' : 'var(--muted)',
                  }}
                >
                  {isTop ? '★' : String(index + 1).padStart(2, '0')}
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
