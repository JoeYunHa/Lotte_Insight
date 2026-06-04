export class HttpError extends Error {
  readonly status: number
  readonly path: string

  constructor(path: string, status: number, method = 'GET') {
    super(`${method} ${path} failed with HTTP ${status}`)
    this.name = 'HttpError'
    this.status = status
    this.path = path
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export function hasApiBase(): boolean {
  return API_BASE.length > 0
}

function ensureApiBase(): string {
  if (!hasApiBase()) {
    throw new Error('NEXT_PUBLIC_API_URL is not configured')
  }
  return API_BASE
}

export function buildApiUrl(path: string): string {
  return `${ensureApiBase()}${path}`
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
  method = 'GET',
): Promise<T> {
  const res = await fetch(buildApiUrl(path), init)
  if (!res.ok) {
    throw new HttpError(path, res.status, method)
  }
  return res.json() as Promise<T>
}

export async function requestJsonOrNull<T>(
  path: string,
  init?: RequestInit,
  method = 'GET',
): Promise<T | null> {
  const res = await fetch(buildApiUrl(path), init)
  if (res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new HttpError(path, res.status, method)
  }
  return res.json() as Promise<T>
}
