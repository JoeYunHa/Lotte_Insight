// Pure presentational badge components — server-renderable.

import { LABEL_META, STANCE_META } from '@/lib/label-config'
import { getToneBadgeStyle } from '@/lib/label-config'
import type { LabelKey, LotteStance } from '@/lib/types'

export function LabelBadge({ label }: { label: LabelKey }) {
  const { name, dot, tone } = LABEL_META[label]
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium leading-none" style={getToneBadgeStyle(tone)}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: dot }} />
      {name}
    </span>
  )
}

export function StanceBadge({ stance }: { stance: LotteStance }) {
  const { label, symbol, tone } = STANCE_META[stance]
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium leading-none" style={getToneBadgeStyle(tone)}>
      <span className="text-[10px]">{symbol}</span>
      {label}
    </span>
  )
}
