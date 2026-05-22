import type { LabelKey, LotteStance } from './types'

export interface LabelMeta {
  name: string
  dot: string
  badge: string   // Tailwind classes for badge
}

export const LABEL_META: Record<LabelKey, LabelMeta> = {
  MATCH_RELATED:        { name: '경기',       dot: '#ef4444', badge: 'bg-red-500/15 text-red-400 border border-red-500/25' },
  INJURY_ROSTER:        { name: '부상·엔트리', dot: '#f59e0b', badge: 'bg-amber-500/15 text-amber-400 border border-amber-500/25' },
  TRANSACTION_CONTRACT: { name: '거래·계약',   dot: '#60a5fa', badge: 'bg-blue-400/15 text-blue-300 border border-blue-400/25' },
  PERFORMANCE_ANALYSIS: { name: '성적 분석',   dot: '#a78bfa', badge: 'bg-violet-500/15 text-violet-400 border border-violet-500/25' },
  INTERVIEW:            { name: '인터뷰',      dot: '#34d399', badge: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25' },
  CLUB_OPERATION:       { name: '구단 운영',   dot: '#22d3ee', badge: 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/25' },
  ETC:                  { name: '기타',        dot: '#94a3b8', badge: 'bg-slate-500/15 text-slate-400 border border-slate-500/25' },
}

export interface StanceMeta {
  label: string
  symbol: string
  badge: string
}

export const STANCE_META: Record<LotteStance, StanceMeta> = {
  positive: { label: '긍정', symbol: '▲', badge: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25' },
  negative: { label: '부정', symbol: '▼', badge: 'bg-red-500/15 text-red-400 border border-red-500/25' },
  neutral:  { label: '중립', symbol: '─', badge: 'bg-slate-600/20 text-slate-400 border border-slate-500/25' },
}

export const ALL_LABELS = Object.keys(LABEL_META) as LabelKey[]
