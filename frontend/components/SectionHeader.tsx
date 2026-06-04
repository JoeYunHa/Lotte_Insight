type SectionAccent = 'red' | 'blue' | 'navy'

interface SectionHeaderProps {
  label: string
  accent?: SectionAccent
  dense?: boolean
}

export function SectionHeader({ label, accent = 'blue', dense = false }: SectionHeaderProps) {
  const labelColor =
    accent === 'red' ? 'var(--red)' :
    accent === 'navy' ? 'var(--text)' :
    'var(--blue)'

  const lineColor =
    accent === 'red'
      ? 'linear-gradient(90deg, var(--red), rgba(var(--lotte-red-rgb), 0.08))'
      : accent === 'navy'
        ? 'linear-gradient(90deg, var(--text), rgba(var(--lotte-navy-rgb), 0.08))'
        : 'linear-gradient(90deg, var(--blue), rgba(var(--lotte-blue-rgb), 0.08))'

  return (
    <div className={`flex items-center gap-3 ${dense ? 'mb-3' : 'mb-5'}`}>
      <span
        className={`shrink-0 rounded-sm ${accent === 'red' ? 'h-4 w-1' : 'h-3.5 w-3.5'}`}
        style={{
          background:
            accent === 'red'
              ? 'var(--red)'
              : accent === 'navy'
                ? 'var(--gradient-navy-band)'
                : 'linear-gradient(180deg, rgba(var(--lotte-blue-rgb), 0.92), rgba(var(--lotte-navy-rgb), 0.9))',
        }}
      />
      {accent === 'navy' ? (
        <span
          className="h-px w-8 shrink-0"
          style={{ background: 'rgba(var(--lotte-red-rgb), 0.55)' }}
        />
      ) : null}
      <span
        className="text-[10px] font-bold tracking-widest uppercase font-mono-code shrink-0"
        style={{ color: labelColor }}
      >
        {label}
      </span>
      <div className="flex-1 h-px" style={{ background: lineColor }} />
    </div>
  )
}
