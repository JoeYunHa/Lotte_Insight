import type { ReactNode } from 'react'
import Link from 'next/link'

interface HeaderAction {
  href: string
  label: string
}

interface PageShellProps {
  children: ReactNode
  footer?: ReactNode
  headerAction?: HeaderAction
  seasonBadge?: string
}

export function PageShell({
  children,
  footer,
  headerAction,
  seasonBadge,
}: PageShellProps) {
  return (
    <div className="min-h-dvh" style={{ background: 'var(--bg)' }}>
      <div className="h-[3px] w-full" style={{ background: 'var(--red)' }} />

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
            {seasonBadge ? (
              <span
                className="text-xs px-1.5 py-0.5 rounded font-mono-code"
                style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
              >
                {seasonBadge}
              </span>
            ) : null}
          </div>
          {headerAction ? (
            <nav className="flex items-center gap-4">
              <Link
                href={headerAction.href}
                className="text-xs transition-colors hover:text-cream-100"
                style={{ color: 'var(--muted)' }}
              >
                {headerAction.label}
              </Link>
            </nav>
          ) : null}
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 pb-20">{children}</main>

      {footer ? <footer className="text-center pb-8">{footer}</footer> : null}
    </div>
  )
}
