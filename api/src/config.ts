export const config = {
  port: parseInt(process.env.API_PORT || '3001'),
  databaseUrl: process.env.DATABASE_URL || '',
  redisUrl: process.env.REDIS_URL || 'redis://redis:6379',
  apiKey: process.env.API_KEY || 'change-me',
  dashboardUrl: process.env.DASHBOARD_URL || 'http://localhost:5173',
  agentUrl: process.env.AGENT_URL || 'http://agent:8000',
}
