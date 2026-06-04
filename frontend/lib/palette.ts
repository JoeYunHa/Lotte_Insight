import type { CSSProperties } from 'react'

export type PaletteTone = 'red' | 'blue' | 'navy' | 'cream' | 'neutral'

export const palette = {
  red: 'var(--red)',
  redDark: 'var(--red-dark)',
  blue: 'var(--blue)',
  blueDeep: 'var(--neutral)',
  navy: 'var(--text)',
  cream: 'var(--surface)',
  creamDeep: 'var(--surface-2)',
  muted: 'var(--muted)',
  dim: 'var(--dim)',
  border: 'var(--border)',
  textOnAccent: 'var(--text-on-accent)',
} as const

const toneStyles: Record<PaletteTone, CSSProperties> = {
  red: { background: 'var(--red-soft)', color: 'var(--red)', border: '1px solid var(--red-border)' },
  blue: { background: 'var(--blue-soft)', color: 'var(--blue)', border: '1px solid var(--blue-border)' },
  navy: { background: 'var(--navy-soft)', color: 'var(--text)', border: '1px solid var(--navy-border)' },
  cream: { background: 'var(--cream-soft)', color: 'var(--text)', border: '1px solid var(--cream-border)' },
  neutral: { background: 'var(--blue-soft)', color: 'var(--neutral)', border: '1px solid var(--blue-border)' },
}

export function getBadgeStyle(tone: PaletteTone): CSSProperties {
  return toneStyles[tone]
}

export function getBadgeDot(tone: PaletteTone): string {
  return tone === 'neutral' ? palette.blueDeep : palette[tone]
}

export const clusterPalette = [
  palette.red,
  palette.blue,
  palette.navy,
  palette.blueDeep,
  'var(--lotte-red-light)',
  'var(--lotte-blue-deep)',
  palette.redDark,
  'var(--lotte-navy-soft)',
]
