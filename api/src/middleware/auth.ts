import { Request, Response, NextFunction } from 'express'
import { config } from '../config'

export function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  // Skip auth for health endpoint
  if (req.path === '/health') {
    next()
    return
  }

  // Skip auth for WebSocket upgrade requests
  if (req.headers.upgrade && req.headers.upgrade.toLowerCase() === 'websocket') {
    next()
    return
  }

  const authHeader = req.headers['authorization']
  if (!authHeader) {
    res.status(401).json({ error: 'Missing Authorization header', code: 'AUTH_MISSING' })
    return
  }

  const parts = authHeader.split(' ')
  if (parts.length !== 2 || parts[0] !== 'Bearer') {
    res.status(401).json({ error: 'Invalid Authorization format. Expected: Bearer <token>', code: 'AUTH_INVALID_FORMAT' })
    return
  }

  const token = parts[1]
  if (token !== config.apiKey) {
    res.status(401).json({ error: 'Invalid API key', code: 'AUTH_INVALID_KEY' })
    return
  }

  next()
}
