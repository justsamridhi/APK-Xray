import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const reportContract = {
  schemaVersion: '1.0',
  reportId: 'report:test',
  generatedAt: '2026-01-01T00:00:00Z',
  app: { minSdk: 1, targetSdk: 1, permissions: [], components: [] },
  score: { breakdown: [] },
  claims: [{
    id: 'claim:test',
    text: { en: 'The app declares network access.', hi: 'ऐप नेटवर्क एक्सेस घोषित करता है।' },
    classification: 'Can',
    evidenceIds: ['manifest:permission:android.permission.INTERNET'],
    status: 'verified',
  }],
}

describe('application routes', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the analyze page at the root route', () => {
    window.history.replaceState({}, '', '/')
    render(<App />)
    expect(screen.getByRole('heading', { name: /evidence-first android static analysis/i })).toBeInTheDocument()
  })

  it('validates APK type before upload', () => {
    window.history.replaceState({}, '', '/analyze')
    render(<App />)
    fireEvent.change(screen.getByLabelText('Choose APK file'), { target: { files: [new File(['not an apk'], 'notes.txt', { type: 'text/plain' })] } })
    expect(screen.getByRole('alert')).toHaveTextContent(/android apk file/i)
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled()
  })

  it('renders the report returned by upload without a second request', async () => {
    window.history.replaceState({}, '', '/analyze')
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...reportContract,
      app: { ...reportContract.app, name: 'Uploaded App', packageName: 'org.uploaded.app', version: '1.0.0' },
      score: { ...reportContract.score, value: 0, label: 'Low exposure', severity: 'low' },
      findings: [],
      capabilityChains: [],
    }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await user.upload(screen.getByLabelText('Choose APK file'), new File(['apk bytes'], 'sample.apk', { type: 'application/vnd.android.package-archive' }))
    await user.click(screen.getByRole('button', { name: 'Start analysis' }))
    expect(await screen.findByRole('heading', { name: 'Uploaded App' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/upload', expect.objectContaining({ method: 'POST' }))
  })

  it('does not fetch a process-wide report when opened directly', async () => {
    window.history.replaceState({}, '', '/report')
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByText(/no report yet/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('renders the sample report separately from a real report', () => {
    window.history.replaceState({}, '', '/report/sample')
    render(<App />)
    expect(screen.getByRole('alert')).toHaveTextContent('Sample data. This is not a real analysis.')
    expect(screen.getByRole('heading', { name: 'Example Lantern' })).toBeInTheDocument()
  })

  it('moves focus into the sample evidence drawer and restores it on close', async () => {
    window.history.replaceState({}, '', '/report/sample')
    const user = userEvent.setup()
    render(<App />)
    const trigger = screen.getAllByRole('button', { name: 'View evidence' })[0]
    await user.click(trigger)
    const close = screen.getByRole('button', { name: 'Close evidence' })
    expect(close).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
  })

  it('switches themes and persists the explicit choice', async () => {
    window.history.replaceState({}, '', '/analyze')
    localStorage.clear()
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(localStorage.getItem('apk-xray-theme')).toBe('dark')
  })
})
