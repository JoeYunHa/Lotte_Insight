import type { PlayerStatus } from './types'

export const ACTIVE_STATUS: PlayerStatus = 'active'

export const PLAYER_STATUS_META: Record<PlayerStatus, { label: string; color: string }> = {
  active: { label: 'Active', color: 'var(--gold)' },
  '1군': { label: 'Active', color: 'var(--gold)' },
  '2군': { label: 'Reserve', color: 'var(--dim)' },
  '말소': { label: 'Inactive', color: 'var(--dim)' },
}

export const PLAYER_STATUS_BADGE: Record<PlayerStatus, { bg: string; text: string; border: string }> = {
  active: { bg: 'rgba(52,211,153,0.12)', text: '#34d399', border: 'rgba(52,211,153,0.25)' },
  '1군': { bg: 'rgba(52,211,153,0.12)', text: '#34d399', border: 'rgba(52,211,153,0.25)' },
  '2군': { bg: 'rgba(148,163,184,0.12)', text: '#94a3b8', border: 'rgba(148,163,184,0.25)' },
  '말소': { bg: 'rgba(248,113,113,0.12)', text: '#f87171', border: 'rgba(248,113,113,0.25)' },
}

export function isActiveStatus(status: string): boolean {
  return status === ACTIVE_STATUS || status === '1군'
}

export function toKnownPlayerStatus(status: string): PlayerStatus {
  if (status === 'active' || status === '1군' || status === '2군' || status === '말소') {
    return status
  }
  return '2군'
}
