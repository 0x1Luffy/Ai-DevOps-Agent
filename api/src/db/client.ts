import { Pool, QueryResult, QueryResultRow } from 'pg'
import { config } from '../config'

export const pool = new Pool({
  connectionString: config.databaseUrl,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
})

pool.on('error', (err: Error) => {
  console.error(`[${new Date().toISOString()}] Unexpected PostgreSQL pool error:`, err.message)
})

export async function query<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: unknown[]
): Promise<QueryResult<T>> {
  const start = Date.now()
  const result = await pool.query<T>(text, params)
  const duration = Date.now() - start
  if (duration > 1000) {
    console.warn(`[${new Date().toISOString()}] Slow query (${duration}ms): ${text.substring(0, 100)}`)
  }
  return result
}

export async function testConnection(): Promise<boolean> {
  try {
    await pool.query('SELECT 1')
    return true
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error(`[${new Date().toISOString()}] PostgreSQL connection test failed:`, message)
    return false
  }
}
