import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('application routes', () => {
  it('renders the analyze shell by default', () => {
    window.history.replaceState({}, '', '/analyze')
    render(<App />)
    expect(screen.getByRole('heading', { name: /evidence-first android static analysis/i })).toBeInTheDocument()
    expect(screen.getByText(/no apk has been uploaded or analyzed/i)).toBeInTheDocument()
  })

  it('renders the report placeholder', () => {
    window.history.replaceState({}, '', '/report')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Analysis report' })).toBeInTheDocument()
    expect(screen.getByText(/no report yet/i)).toBeInTheDocument()
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
