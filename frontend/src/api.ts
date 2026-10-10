import { normalizeReport, type ReportData } from './report'

export const maxApkSize = 50 * 1024 * 1024
const defaultUploadEndpoint = '/api/upload'

export type UploadErrorCode = 'cancelled' | 'timeout' | 'network' | 'http' | 'invalid_response'

export class UploadError extends Error {
  constructor(public readonly code: UploadErrorCode, message: string) {
    super(message)
    this.name = 'UploadError'
  }
}

function errorMessage(status: number, payload: unknown): string {
  if (payload && typeof payload === 'object') {
    const error = (payload as { error?: { message?: unknown } }).error
    if (error && typeof error.message === 'string' && error.message.trim()) return error.message
  }
  return `The analysis service returned HTTP ${status}.`
}

export async function upload(file: File, signal: AbortSignal, endpoint = import.meta.env.VITE_API_UPLOAD_URL ?? defaultUploadEndpoint): Promise<ReportData> {
  const body = new FormData()
  body.append('file', file)
  let response: Response
  try {
    response = await fetch(endpoint, { method: 'POST', body, signal })
  } catch (error) {
    if (signal.reason instanceof DOMException && signal.reason.name === 'TimeoutError') throw new UploadError('timeout', 'The analysis request timed out. Try again.')
    if (signal.aborted) throw new UploadError('cancelled', 'Analysis cancelled.')
    if (error instanceof DOMException && error.name === 'TimeoutError') throw new UploadError('timeout', 'The analysis request timed out. Try again.')
    throw new UploadError('network', 'The analysis service could not be reached. Check that the backend is running.')
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new UploadError('invalid_response', 'The analysis service returned invalid JSON.')
  }
  if (!response.ok) throw new UploadError('http', errorMessage(response.status, payload))
  const report = normalizeReport(payload)
  if (!report) throw new UploadError('invalid_response', 'The analysis service returned an invalid report.')
  return report
}
