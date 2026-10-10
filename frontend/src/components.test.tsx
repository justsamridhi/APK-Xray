import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Badge, Header, PrimaryButton } from './components'

describe('shared components', () => {
  it('renders accessible button states and badge tones', () => {
    render(<><PrimaryButton disabled>Analyze APK</PrimaryButton><Badge tone="warning">WARNING</Badge></>)
    expect(screen.getByRole('button', { name: 'Analyze APK' })).toBeDisabled()
    expect(screen.getByText('WARNING')).toHaveClass('badge-warning')
  })

  it('marks the active navigation page', async () => {
    const user = userEvent.setup()
    render(<Header currentPath="/analyze" />)
    expect(screen.getByRole('link', { name: /analyze/i })).toHaveAttribute('aria-current', 'page')
    await user.tab()
    expect(document.activeElement).toHaveAttribute('href', '/analyze')
  })
})
