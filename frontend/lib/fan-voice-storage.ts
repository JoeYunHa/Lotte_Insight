const CLEAN_MODE_KEY = 'fan-voice-clean-mode'

export function readCleanMode(): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(CLEAN_MODE_KEY) === '1'
}

export function writeCleanMode(value: boolean): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(CLEAN_MODE_KEY, value ? '1' : '0')
}
