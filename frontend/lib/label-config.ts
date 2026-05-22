import type { LabelKey, LotteStance } from './types'

export interface LabelMeta {
  name: string
  dot: string
  badge: string
}

export const LABEL_META: Record<LabelKey, LabelMeta> = {
  MATCH_RELATED: { name: 'Match', dot: '#ef4444', badge: 'bg-red-500/15 text-red-500 border border-red-500/25' },
  INJURY_ROSTER: { name: 'Injury/Roster', dot: '#f59e0b', badge: 'bg-amber-500/15 text-amber-600 border border-amber-500/25' },
  TRANSACTION_CONTRACT: { name: 'Transaction', dot: '#60a5fa', badge: 'bg-blue-400/15 text-blue-600 border border-blue-400/25' },
  PERFORMANCE_ANALYSIS: { name: 'Performance', dot: '#a78bfa', badge: 'bg-violet-500/15 text-violet-600 border border-violet-500/25' },
  INTERVIEW: { name: 'Interview', dot: '#34d399', badge: 'bg-emerald-500/15 text-emerald-600 border border-emerald-500/25' },
  CLUB_OPERATION: { name: 'Club', dot: '#22d3ee', badge: 'bg-cyan-500/15 text-cyan-600 border border-cyan-500/25' },
  ETC: { name: 'General', dot: '#94a3b8', badge: 'bg-slate-500/15 text-slate-600 border border-slate-500/25' },
}

export interface StanceMeta {
  label: string
  symbol: string
  badge: string
}

export const STANCE_META: Record<LotteStance, StanceMeta> = {
  positive: { label: 'Positive', symbol: '+', badge: 'bg-emerald-500/15 text-emerald-600 border border-emerald-500/25' },
  negative: { label: 'Negative', symbol: '-', badge: 'bg-red-500/15 text-red-500 border border-red-500/25' },
  neutral: { label: 'Neutral', symbol: '=', badge: 'bg-slate-600/15 text-slate-600 border border-slate-500/25' },
}

export const ALL_LABELS = Object.keys(LABEL_META) as LabelKey[]

export function getLabelMeta(label: string | null | undefined): LabelMeta | null {
  if (!label || !(label in LABEL_META)) return null
  return LABEL_META[label as LabelKey]
}
