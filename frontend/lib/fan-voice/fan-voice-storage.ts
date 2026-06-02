const CLEAN_MODE_KEY = 'fan-voice-clean-mode'
const SESSION_TOKEN_KEY = 'fan-voice-session-token'

export function readCleanMode(): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(CLEAN_MODE_KEY) === '1'
}

export function writeCleanMode(value: boolean): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(CLEAN_MODE_KEY, value ? '1' : '0')
}

export function readSessionToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(SESSION_TOKEN_KEY)
}

export function writeSessionToken(token: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(SESSION_TOKEN_KEY, token)
}
