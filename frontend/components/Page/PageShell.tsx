import type { ReactNode } from 'react'
import Image from 'next/image'
import Link from 'next/link'

interface HeaderAction {
  href: string
  label: string
}

interface PageShellProps {
  children: ReactNode
  footer?: ReactNode
  headerActions?: HeaderAction[]
  seasonBadge?: string
}

export function PageShell({ children, footer, headerActions, seasonBadge }: PageShellProps) {
  return (
    <div className="min-h-dvh" style={{ background: 'var(--bg)' }}>
      <div className="h-[4px] w-full" style={{ background: 'var(--gradient-navy-band)' }} />

      <header className="sticky top-0 z-50 backdrop-blur-md" style={{ background: 'var(--surface-glass-strong)', borderBottom: '1px solid var(--border)', boxShadow: '0 8px 24px rgba(var(--lotte-navy-rgb), 0.06)' }}>
        <div className="max-w-5xl mx-auto px-4 py-2 min-h-14 flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <Image
              src="/images/lotte_emblem.jpg"
              alt="롯데 자이언츠"
              width={56}
              height={42}
              className="shrink-0 object-contain"
              priority
            />
            <div className="flex min-w-0 flex-col">
              <span className="font-bold text-sm tracking-wide leading-none" style={{ color: 'var(--text)' }}>
                Lotte Insight
              </span>
              <span className="text-[10px] font-mono-code leading-none mt-0.5" style={{ color: 'var(--muted)' }}>
                LOTTE GIANTS MATCHDAY DESK
              </span>
            </div>
            {seasonBadge ? (
              <span className="chip-surface text-xs px-1.5 py-0.5 rounded font-mono-code ml-1" style={{ color: 'var(--text)' }}>
                {seasonBadge}
              </span>
            ) : null}
          </div>
          {headerActions && headerActions.length > 0 ? (
            <nav className="flex flex-wrap items-center justify-end gap-2">
              {headerActions.map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="text-xs transition-all px-3 py-1.5 rounded-full hover:-translate-y-px"
                  style={{
                    color: 'var(--text)',
                    border: '1px solid var(--border)',
                    background: 'var(--surface-glass-muted)',
                  }}
                >
                  {action.label}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 pb-24">{children}</main>
      {footer ? <footer className="text-center pb-8">{footer}</footer> : null}
    </div>
  )
}
