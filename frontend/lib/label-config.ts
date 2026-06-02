import type { CSSProperties } from 'react'
import { getBadgeDot, getBadgeStyle, type PaletteTone } from './palette'
import type { LabelKey, LotteStance } from './types'

export interface LabelMeta {
  name: string
  dot: string
  tone: PaletteTone
}

export const LABEL_META: Record<LabelKey, LabelMeta> = {
  MATCH_RELATED: { name: 'Match', dot: getBadgeDot('red'), tone: 'red' },
  INJURY_ROSTER: { name: 'Injury/Roster', dot: getBadgeDot('gold'), tone: 'gold' },
  TRANSACTION_CONTRACT: { name: 'Transaction', dot: getBadgeDot('blue'), tone: 'blue' },
  PERFORMANCE_ANALYSIS: { name: 'Performance', dot: getBadgeDot('navy'), tone: 'navy' },
  INTERVIEW: { name: 'Interview', dot: getBadgeDot('blue'), tone: 'blue' },
  CLUB_OPERATION: { name: 'Club', dot: getBadgeDot('gold'), tone: 'gold' },
  ETC: { name: 'General', dot: getBadgeDot('neutral'), tone: 'neutral' },
}

export interface StanceMeta {
  label: string
  symbol: string
  tone: PaletteTone
}

export const STANCE_META: Record<LotteStance, StanceMeta> = {
  positive: { label: 'Positive', symbol: '+', tone: 'gold' },
  negative: { label: 'Negative', symbol: '-', tone: 'red' },
  neutral: { label: 'Neutral', symbol: '=', tone: 'neutral' },
}

export function getToneBadgeStyle(tone: PaletteTone): CSSProperties {
  return getBadgeStyle(tone)
}

export const ALL_LABELS = Object.keys(LABEL_META) as LabelKey[]

export function getLabelMeta(label: string | null | undefined): LabelMeta | null {
  if (!label || !(label in LABEL_META)) return null
  return LABEL_META[label as LabelKey]
}
