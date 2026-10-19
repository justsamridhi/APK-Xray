import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE } from './config'
import { upload, UploadError } from './api'

const report = {
  schemaVersion: '1.0',
  reportId: 'report:test',
  generatedAt: '2026-01-01T00:00:00Z',
  app: { name: 'Test', packageName: 'org.test.app', version: '1', minSdk: 1, targetSdk: 1, permissions: [], components: [] },
  score: { value: 0, label: 'Low', severity: 'low', breakdown: [] },
  findings: [],
  capabilityChains: [],
  claims: [],
}

describe('upload API client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('posts the APK under the backend field name and validates the report', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(report), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['apk'], 'sample.apk', { type: 'application/vnd.android.package-archive' })
    await expect(upload(file, new AbortController().signal)).resolves.toMatchObject({ app: { packageName: 'org.test.app' } })
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/upload`, expect.objectContaining({ method: 'POST', body: expect.any(FormData) }))
    const requestBody = (fetchMock.mock.calls[0][1] as RequestInit).body
    expect(requestBody).toBeInstanceOf(FormData)
    if (!(requestBody instanceof FormData)) throw new Error('Expected a FormData request body.')
    expect(requestBody.get('file')).toBe(file)
  })

  it('classifies HTTP and malformed responses safely', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: 'Bad upload' } }), { status: 415 })))
    await expect(upload(new File(['apk'], 'a.apk'), new AbortController().signal)).rejects.toMatchObject({ code: 'http', message: 'Bad upload' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{broken', { status: 200 })))
    await expect(upload(new File(['apk'], 'a.apk'), new AbortController().signal)).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it('classifies cancellation and network failures', async () => {
    const controller = new AbortController()
    controller.abort()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError')))
    await expect(upload(new File(['apk'], 'a.apk'), controller.signal)).rejects.toBeInstanceOf(UploadError)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(upload(new File(['apk'], 'a.apk'), new AbortController().signal)).rejects.toMatchObject({ code: 'network' })
  })
})
