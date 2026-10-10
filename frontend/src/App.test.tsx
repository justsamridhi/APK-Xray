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
  claims: [],
}

describe('application routes', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the analyze page at the root route', () => {
    window.history.replaceState({}, '', '/')
    render(<App />)
    expect(screen.getByRole('heading', { name: /evidence-first android static analysis/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Analyze' })[0]).toHaveAttribute('href', '/')
  })

  it('renders the analyze upload flow', () => {
    window.history.replaceState({}, '', '/analyze')
    render(<App />)
    expect(screen.getByRole('heading', { name: /evidence-first android static analysis/i })).toBeInTheDocument()
    expect(screen.getByText(/maximum size 50 mb/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled()
  })

  it('validates APK type before upload', () => {
    window.history.replaceState({}, '', '/analyze')
    render(<App />)
    fireEvent.change(screen.getByLabelText('Choose APK file'), { target: { files: [new File(['not an apk'], 'notes.txt', { type: 'text/plain' })] } })
    expect(screen.getByRole('alert')).toHaveTextContent(/android apk file/i)
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled()
  })

  it('uploads a valid APK and navigates to the report', async () => {
    window.history.replaceState({}, '', '/analyze')
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...reportContract,
      app: { ...reportContract.app, name: 'Uploaded App', packageName: 'org.uploaded.app', version: '1.0.0' },
      score: { ...reportContract.score, value: 0, label: 'Low exposure', severity: 'low' },
      findings: [],
      capabilityChains: [],
    }), { status: 200 })))
    render(<App />)
    await user.upload(screen.getByLabelText('Choose APK file'), new File(['apk bytes'], 'sample.apk', { type: 'application/vnd.android.package-archive' }))
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Start analysis' }))
    expect(await screen.findByRole('heading', { name: 'Uploaded App' })).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/upload', expect.objectContaining({ method: 'POST' }))
  })

  it('renders the report placeholder', async () => {
    window.history.replaceState({}, '', '/report')
    sessionStorage.clear()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 404 })))
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Analysis report' })).toBeInTheDocument()
    expect(await screen.findByText(/no report yet/i)).toBeInTheDocument()
  })

  it('renders a fetched report and opens evidence', async () => {
    window.history.replaceState({}, '', '/report')
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...reportContract,
      app: { ...reportContract.app, name: 'Test App', packageName: 'org.test.app', version: '1.2.3' },
      score: { ...reportContract.score, value: 48, label: 'Backend-calculated moderate exposure', severity: 'moderate' },
      findings: [{ ruleId: 'RULE-1', severity: 'medium', title: 'Exported component', summary: 'Review this component.', points: 12, claimStatus: 'verified', explanations: { en: 'The component is exported.', hi: 'घटक एक्सपोर्ट किया गया है।' }, evidence: [{ id: 'E-1', label: 'AndroidManifest.xml', snippet: 'exported=true', availability: 'available' }] }],
      capabilityChains: [{ id: 'C1', label: 'Export path', steps: [{ id: 'step-1', label: 'Manifest component', evidenceId: 'E-1' }] }],
    }), { status: 200 })))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Test App' })).toBeInTheDocument()
    expect(screen.getByText('12 points')).toBeInTheDocument()
    expect(screen.getByText('MODERATE')).toBeInTheDocument()
    expect(screen.getByText('The component is exported.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'हिन्दी' }))
    expect(screen.getByText('घटक एक्सपोर्ट किया गया है।')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Manifest component/ }))
    expect(screen.getByRole('dialog')).toHaveTextContent('E-1')
    await user.click(screen.getByRole('button', { name: 'Close evidence' }))
    await user.click(screen.getByRole('button', { name: 'View evidence' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('E-1')
    expect(screen.getByRole('dialog')).toHaveTextContent('exported=true')
    await user.click(screen.getByRole('button', { name: 'Close evidence' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('traps focus and restores it in the production evidence drawer', async () => {
    window.history.replaceState({}, '', '/report')
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...reportContract,
      app: { ...reportContract.app, name: 'Test App', packageName: 'org.test.app', version: '1.2.3' },
      score: { ...reportContract.score, value: 20, label: 'Low', severity: 'low' },
      findings: [{ ruleId: 'RULE-1', severity: 'low', title: 'Finding', summary: 'Summary', evidence: [], claimStatus: 'unavailable', points: null, explanations: { en: null, hi: null } }],
    }), { status: 200 })))
    render(<App />)
    await screen.findByRole('heading', { name: 'Test App' })
    const trigger = screen.getByRole('button', { name: 'View evidence' })
    await user.click(trigger)
    const close = screen.getByRole('button', { name: 'Close evidence' })
    expect(close).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
  })

  it('shows an error for malformed report responses', async () => {
    window.history.replaceState({}, '', '/report')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{broken', { status: 200 })))
    render(<App />)
    expect(await screen.findByText('Report unavailable')).toBeInTheDocument()
  })

  it('renders the sample report separately from the real report', async () => {
    window.history.replaceState({}, '', '/report/sample')
    render(<App />)
    expect(screen.getByRole('alert')).toHaveTextContent('Sample data. This is not a real analysis.')
    expect(screen.getByRole('heading', { name: 'Example Lantern' })).toBeInTheDocument()
    expect(screen.queryByText('No report yet')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
    expect(screen.getByRole('alert')).toHaveTextContent('उदाहरण डेटा। यह वास्तविक विश्लेषण नहीं है।')
    expect(screen.getByText(/कर सकता है/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'उदाहरण नियम परिणाम' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'उदाहरण अनुमति संयोजन' })).toBeInTheDocument()
    expect(screen.getByText(/घोषित अनुमतियों का एक काल्पनिक संयोजन/)).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'साक्ष्य देखें' })[0])
    expect(screen.getByText(/android.permission.READ_EXAMPLE और/)).toBeInTheDocument()
  })

  it('moves focus into the evidence drawer, traps it, and restores it on close', async () => {
    window.history.replaceState({}, '', '/report/sample')
    const user = userEvent.setup()
    render(<App />)
    const trigger = screen.getAllByRole('button', { name: 'View evidence' })[0]
    await user.click(trigger)
    const close = screen.getByRole('button', { name: 'Close evidence' })
    expect(close).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('renders the About page', () => {
    window.history.replaceState({}, '', '/about')
    render(<App />)
    expect(screen.getByRole('heading', { name: /inspect first/i })).toBeInTheDocument()
    expect(screen.getByText(/static-analysis pipeline/i)).toBeInTheDocument()
  })

  it('switches themes and persists the explicit choice', async () => {
    window.history.replaceState({}, '', '/analyze')
    localStorage.clear()
    render(<App />)
    const toggle = screen.getByRole('button', { name: 'Switch to dark theme' })
    await userEvent.click(toggle)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(localStorage.getItem('apk-xray-theme')).toBe('dark')
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument()
  })
})
