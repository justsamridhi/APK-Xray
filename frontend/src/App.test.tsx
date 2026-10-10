import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

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
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })))
    render(<App />)
    await user.upload(screen.getByLabelText('Choose APK file'), new File(['apk bytes'], 'sample.apk', { type: 'application/vnd.android.package-archive' }))
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Start analysis' }))
    expect(await screen.findByRole('heading', { name: 'Analysis report' })).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/upload', expect.objectContaining({ method: 'POST' }))
  })

  it('renders the report placeholder', () => {
    window.history.replaceState({}, '', '/report')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Analysis report' })).toBeInTheDocument()
    expect(screen.getByText(/no report yet/i)).toBeInTheDocument()
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
