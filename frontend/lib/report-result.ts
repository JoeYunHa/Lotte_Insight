import type { TeamDailyReport } from './types'

export type GameResultDisplay = 'W' | 'L' | 'D' | null

const WIN_PATTERNS = ['승리', '이겼', '완승', '연승']
const LOSS_PATTERNS = ['패배', '졌', '완패', '연패']
const DRAW_PATTERNS = ['무승부', '연장 무']

function containsAny(text: string, patterns: string[]): boolean {
  return patterns.some((pattern) => text.includes(pattern))
}

export function inferGameResult(report: TeamDailyReport): GameResultDisplay {
  const summary = report.issue_summary ?? ''
  if (containsAny(summary, WIN_PATTERNS)) return 'W'
  if (containsAny(summary, LOSS_PATTERNS)) return 'L'
  if (containsAny(summary, DRAW_PATTERNS)) return 'D'
  return null
}
