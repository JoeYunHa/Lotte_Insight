import type { ReactNode } from 'react'
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
      <div className="h-[3px] w-full" style={{ background: 'var(--red)' }} />

      <header className="sticky top-0 z-50 backdrop-blur-md" style={{ background: 'rgba(251, 246, 239, 0.9)', borderBottom: '1px solid var(--border)' }}>
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl flex flex-col items-center justify-center gap-0 shrink-0" style={{ background: 'var(--red)', color: '#fff' }}>
              <span className="text-sm font-bold leading-none">L</span>
              <span className="text-[7px] font-bold tracking-widest leading-none opacity-80">DESK</span>
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-sm tracking-wide leading-none" style={{ color: 'var(--text)' }}>
                Lotte Insight
              </span>
              <span className="text-[10px] font-mono-code leading-none mt-0.5" style={{ color: 'var(--muted)' }}>
                LOTTE GIANTS MATCHDAY DESK
              </span>
            </div>
            {seasonBadge ? (
              <span className="text-xs px-1.5 py-0.5 rounded font-mono-code ml-1" style={{ background: 'var(--surface-2)', color: 'var(--muted)', border: '1px solid var(--border)' }}>
                {seasonBadge}
              </span>
            ) : null}
          </div>
          {headerActions && headerActions.length > 0 ? (
            <nav className="flex items-center gap-2">
              {headerActions.map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="text-xs transition-colors px-3 py-1.5 rounded-full"
                  style={{
                    color: 'var(--muted)',
                    border: '1px solid var(--border)',
                    background: 'rgba(255,255,255,0.72)',
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
