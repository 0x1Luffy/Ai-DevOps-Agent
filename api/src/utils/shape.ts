export function toCamel(value: unknown): unknown {
  if (value === null || value === undefined) return value
  if (value instanceof Date) return value.toISOString()
  if (Array.isArray(value)) return value.map((item) => toCamel(item))
  if (typeof value !== 'object') return value

  const out: Record<string, unknown> = {}
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    const camelKey = key.replace(/_([a-z])/g, (_, ch: string) => ch.toUpperCase())
    out[camelKey] = toCamel(item)
  }
  return out
}

export function normalizeResult(result: string | null): string | null {
  if (result === 'failure') return 'failed'
  return result
}

export function ratio(success: number, total: number): number {
  return total > 0 ? Number((success / total).toFixed(4)) : 0
}
