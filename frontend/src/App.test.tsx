import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('application routes', () => {
  it('renders the analyze shell by default', () => {
    window.history.replaceState({}, '', '/analyze')
    render(<App />)
    expect(screen.getByRole('heading', { name: /evidence-first android static analysis/i })).toBeInTheDocument()
    expect(screen.getByText(/demo data: no apk is uploaded/i)).toBeInTheDocument()
  })

  it('renders the report placeholder', () => {
    window.history.replaceState({}, '', '/report')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Analysis report' })).toBeInTheDocument()
    expect(screen.getByText(/no report available/i)).toBeInTheDocument()
  })
})
