import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Badge, NavigationLayout, PrimaryButton } from './ui-components'
import { UX4GLanguageSelector, InfographicDonut, InfographicPipelineSteps, InfographicFindingCard } from './components'

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

  it('renders UX4G multilingual language selector and updates lang attribute', async () => {
    const user = userEvent.setup()
    const onLanguageChange = vi.fn()
    const { rerender } = render(
      <UX4GLanguageSelector
        currentLanguage="en"
        onLanguageChange={onLanguageChange}
        label="Explanation language"
      />,
    )
    expect(screen.getByRole('group', { name: 'Explanation language' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
    const hindiBtn = screen.getByRole('button', { name: 'हिन्दी' })
    const englishBtn = screen.getByRole('button', { name: 'English' })
    expect(englishBtn).toHaveAttribute('aria-pressed', 'true')
    expect(hindiBtn).toHaveAttribute('aria-pressed', 'false')

    await user.click(hindiBtn)
    expect(onLanguageChange).toHaveBeenCalledWith('hi')

    rerender(
      <UX4GLanguageSelector
        currentLanguage="hi"
        onLanguageChange={onLanguageChange}
        label="Explanation language"
      />,
    )
    expect(document.documentElement.lang).toBe('hi')
    expect(hindiBtn).toHaveAttribute('aria-pressed', 'true')
    expect(englishBtn).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders infographic donut and pipeline steps', () => {
    render(
      <>
        <InfographicDonut
          score={72}
          severity="high"
          label="High exposure detected"
          findings={[
            {
              ruleId: 'TEST-1',
              severity: 'high',
              title: 'High severity issue',
              summary: 'Summary high',
              evidence: [],
              claimStatus: 'verified',
              points: 30,
              explanations: { en: 'Explanation en', hi: 'व्याख्या' },
            },
            {
              ruleId: 'TEST-2',
              severity: 'low',
              title: 'Low severity issue',
              summary: 'Summary low',
              evidence: [],
              claimStatus: 'verified',
              points: 5,
              explanations: { en: 'Explanation low', hi: 'व्याख्या' },
            },
          ]}
        />
        <InfographicPipelineSteps />
      </>
    )

    expect(screen.getByText('72')).toBeInTheDocument()
    expect(screen.getByText('/100')).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
    expect(screen.getByText('High Risk')).toBeInTheDocument()
    expect(screen.getByText('Low Risk')).toBeInTheDocument()
    expect(screen.getByText('Parse')).toBeInTheDocument()
    expect(screen.getByText('Rules')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()
    expect(screen.getByText('Report')).toBeInTheDocument()
  })

  it('renders infographic finding card with horizontal progress bar and evidence trigger', async () => {
    const user = userEvent.setup()
    const onEvidence = vi.fn()
    const sampleFinding = {
      ruleId: 'RULE-XYZ',
      severity: 'medium' as const,
      title: 'Exported Service Warning',
      summary: 'Service is open to other apps',
      evidence: [{ id: 'E-99', label: 'Manifest', snippet: 'android:exported="true"' }],
      claimStatus: 'verified' as const,
      points: 25,
      explanations: { en: 'This service allows remote binding.', hi: 'यह सेवा अनुमति देती है।' },
    }

    render(
      <InfographicFindingCard
        index={0}
        finding={sampleFinding}
        language="en"
        onEvidence={onEvidence}
      />
    )

    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('RULE-XYZ')).toBeInTheDocument()
    expect(screen.getByText('Exported Service Warning')).toBeInTheDocument()
    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
    expect(screen.getByText('25 pts')).toBeInTheDocument()
    expect(screen.getByText('This service allows remote binding.')).toBeInTheDocument()

    const btn = screen.getByRole('button', { name: 'View evidence' })
    await user.click(btn)
    expect(onEvidence).toHaveBeenCalledWith(sampleFinding)
  })
})

