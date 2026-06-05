import { Request, Response, NextFunction } from 'express'

export interface AppError extends Error {
  statusCode?: number
  code?: string
}

export function errorHandler(
  err: AppError,
  req: Request,
  res: Response,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _next: NextFunction
): void {
  const timestamp = new Date().toISOString()
  const statusCode = err.statusCode || 500
  const code = err.code || 'INTERNAL_ERROR'

  console.error(`[${timestamp}] Error ${statusCode} on ${req.method} ${req.path}: ${err.message}`)
  if (err.stack && statusCode === 500) {
    console.error(err.stack)
  }

  res.status(statusCode).json({
    error: statusCode === 500 ? 'An internal server error occurred' : err.message,
    code,
  })
}

export function createError(message: string, statusCode: number, code: string): AppError {
  const err: AppError = new Error(message)
  err.statusCode = statusCode
  err.code = code
  return err
}
