type SectionAccent = 'red' | 'gold' | 'neutral'

interface SectionHeaderProps {
  label: string
  accent?: SectionAccent
  dense?: boolean
}

export function SectionHeader({ label, accent = 'neutral', dense = false }: SectionHeaderProps) {
  const labelColor =
    accent === 'red' ? 'var(--red)' :
    accent === 'gold' ? 'var(--gold)' :
    'var(--dim)'

  const lineColor =
    accent === 'red' ? 'var(--red)' :
    accent === 'gold' ? 'var(--gold)' :
    'var(--border)'

  const lineClass = accent === 'red' ? 'h-[2px]' : 'h-px'

  return (
    <div className={`flex items-center gap-3 ${dense ? 'mb-3' : 'mb-5'}`}>
      {accent === 'gold' ? (
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: 'var(--gold)' }}
        />
      ) : null}
      <span
        className="text-[10px] font-bold tracking-widest uppercase font-mono-code shrink-0"
        style={{ color: labelColor }}
      >
        {label}
      </span>
      <div className={`flex-1 ${lineClass}`} style={{ background: lineColor }} />
    </div>
  )
}
