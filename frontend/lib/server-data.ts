export async function withFallback<T>(
  loader: () => Promise<T>,
  fallback: T,
  context: string,
): Promise<T> {
  try {
    return await loader()
  } catch (error) {
    console.error(`[server-data] ${context} failed`, error)
    return fallback
  }
}

export async function withResult<T>(
  loader: () => Promise<T>,
  context: string,
): Promise<{ ok: true; data: T } | { ok: false; data: null }> {
  try {
    return { ok: true, data: await loader() }
  } catch (error) {
    console.error(`[server-data] ${context} failed`, error)
    return { ok: false, data: null }
  }
}
