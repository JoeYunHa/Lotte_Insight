type SectionAccent = 'red' | 'blue' | 'navy'

interface SectionHeaderProps {
  label: string
  accent?: SectionAccent
  dense?: boolean
}

export function SectionHeader({ label, accent = 'blue', dense = false }: SectionHeaderProps) {
  const theme =
    accent === 'red'
      ? {
          plate: 'linear-gradient(135deg, rgba(var(--lotte-red-rgb), 0.92) 0%, rgba(var(--lotte-red-rgb), 0.78) 100%)',
          text: 'var(--lotte-navy)',
          field: 'rgba(var(--lotte-red-rgb), 0.08)',
          border: 'var(--red-border)',
        }
      : accent === 'navy'
        ? {
            plate: 'linear-gradient(135deg, rgba(var(--lotte-navy-rgb), 0.98) 0%, rgba(var(--lotte-blue-rgb), 0.82) 100%)',
            text: 'var(--lotte-navy)',
            field: 'rgba(var(--lotte-blue-rgb), 0.08)',
            border: 'var(--navy-border)',
          }
        : {
            plate: 'linear-gradient(135deg, rgba(var(--lotte-blue-rgb), 0.94) 0%, rgba(var(--lotte-navy-rgb), 0.82) 100%)',
            text: 'var(--lotte-navy)',
            field: 'rgba(var(--lotte-blue-rgb), 0.08)',
            border: 'var(--blue-border)',
          }

  return (
    <div className={`${dense ? 'mb-3' : 'mb-5'}`}>
      <div
        className="flex items-center gap-3 rounded-[18px] px-3 py-3"
        style={{
          background: theme.field,
          border: `1px solid ${theme.border}`,
        }}
      >
        <span
          className="inline-flex rounded-[14px] px-3 py-2 text-[10px] font-bold uppercase tracking-widest font-mono-code"
          style={{ background: theme.plate, color: theme.text }}
        >
          {label}
        </span>
        <div className="h-10 flex-1 rounded-[14px]" style={{ background: 'rgba(var(--lotte-white-rgb), 0.36)' }} />
      </div>
    </div>
  )
}
