import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Badge, NavigationLayout, PrimaryButton } from './components'

describe('shared components', () => {
  it('renders accessible button states and badge tones', () => {
    render(<><PrimaryButton disabled>Analyze APK</PrimaryButton><Badge tone="warning">WARNING</Badge></>)
    expect(screen.getByRole('button', { name: 'Analyze APK' })).toBeDisabled()
    expect(screen.getByText('WARNING')).toHaveClass('badge-warning')
  })

  it('marks the active navigation page', async () => {
    const user = userEvent.setup()
    render(<NavigationLayout currentPath="/analyze" theme="light" onThemeToggle={() => undefined}>content</NavigationLayout>)
    expect(screen.getAllByRole('link', { name: 'Analyze' })[0]).toHaveAttribute('aria-current', 'page')
    await user.tab()
    expect(document.activeElement).toHaveAttribute('href', '/')
  })

  it('exposes an accessible theme toggle', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(<NavigationLayout currentPath="/report" theme="light" onThemeToggle={onToggle}>content</NavigationLayout>)
    const toggle = screen.getByRole('button', { name: 'Switch to dark theme' })
    expect(toggle).toHaveTextContent('Dark mode')
    await user.click(toggle)
    expect(onToggle).toHaveBeenCalledOnce()
  })

  it('supports a collapsible accessible sidebar', async () => {
    const user = userEvent.setup()
    render(<NavigationLayout currentPath="/" theme="light" onThemeToggle={() => undefined}>content</NavigationLayout>)
    const collapse = screen.getByRole('button', { name: 'Collapse navigation' })
    await user.click(collapse)
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByRole('link', { name: 'Analyze' })[0]).toHaveAttribute('title', 'Analyze')
  })
})
