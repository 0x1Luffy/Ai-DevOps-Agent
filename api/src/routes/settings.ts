import { Router, Request, Response, NextFunction } from 'express'
import axios from 'axios'
import { config } from '../config'
import { createError } from '../middleware/errorHandler'

const router = Router()

function agentHeaders() {
  return { 'X-API-Key': config.apiKey }
}

router.get('/config', async (_req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const response = await axios.get(`${config.agentUrl}/settings/config`, {
      timeout: 10000,
      headers: agentHeaders(),
    })
    res.json(response.data)
  } catch (err) {
    if (axios.isAxiosError(err)) {
      return next(createError(`Failed to fetch agent config: ${err.message}`, err.response?.status ?? 503, 'AGENT_UNAVAILABLE'))
    }
    next(err)
  }
})

router.patch('/config', async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const response = await axios.patch(`${config.agentUrl}/settings/config`, req.body, {
      timeout: 10000,
      headers: agentHeaders(),
    })
    res.json(response.data)
  } catch (err) {
    if (axios.isAxiosError(err)) {
      return next(createError(`Failed to update agent config: ${err.message}`, err.response?.status ?? 503, 'AGENT_UNAVAILABLE'))
    }
    next(err)
  }
})

export default router
