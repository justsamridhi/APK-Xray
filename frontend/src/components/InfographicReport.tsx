import { useMemo } from 'react'
import type { ReportData, ReportFinding, ReportLanguage, ReportSeverity } from '../report'

// -----------------------------------------------------------------------
// Color tokens matching the app theme (CSS variables)
// -----------------------------------------------------------------------
const SEV_ORDER: ReportSeverity[] = ['high', 'medium', 'low']

const SEV_LABELS: Record<ReportSeverity, string> = {
  high: 'High Risk',
  medium: 'Medium Risk',
  low: 'Low Risk',
}

// -----------------------------------------------------------------------
// 1. InfographicDonut – Multi-ring concentric donut chart
// -----------------------------------------------------------------------
export interface InfographicDonutProps {
  score: number
  maxScore?: number
  severity: ReportData['score']['severity']
  label?: string
  findings: ReportFinding[]
}

function Ring({
  cx,
  cy,
  r,
  strokeWidth,
  progress,
  className,
}: {
  cx: number
  cy: number
  r: number
  strokeWidth: number
  progress: number // 0 to 1
  className: string
}) {
  const circumference = 2 * Math.PI * r
  const clamped = Math.min(Math.max(progress, 0), 1)
  const offset = circumference * (1 - clamped)

  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill="none"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeDasharray={circumference}
      strokeDashoffset={offset}
      className={className}
      transform={`rotate(-90 ${cx} ${cy})`}
    />
  )
}

export function InfographicDonut({
  score,
  maxScore = 100,
  severity,
  label,
  findings,
}: InfographicDonutProps) {
  const cx = 95
  const cy = 95
  const radii = [76, 60, 44]
  const ringWidth = 10

  const stats = useMemo(() => {
    const total = findings.length || 1
    const highCount = findings.filter((f) => f.severity === 'high').length
    const medCount = findings.filter((f) => f.severity === 'medium').length
    const lowCount = findings.filter((f) => f.severity === 'low').length

    return {
      total: findings.length,
      high: { count: highCount, pct: Math.round((highCount / total) * 100), ratio: highCount / total },
      medium: { count: medCount, pct: Math.round((medCount / total) * 100), ratio: medCount / total },
      low: { count: lowCount, pct: Math.round((lowCount / total) * 100), ratio: lowCount / total },
    }
  }, [findings])

  const scoreFormatted = severity.replace('-', ' ').toUpperCase()

  return (
    <div className="infographic-donut-container" aria-label={`Exposure score: ${score} of ${maxScore}`}>
      <div className="infographic-donut-chart-box">
        <svg
          className="infographic-donut-svg"
          viewBox="0 0 190 190"
          width="190"
          height="190"
          aria-hidden="true"
        >
          {/* Background tracks */}
          {radii.map((r, i) => (
            <circle
              key={`track-${i}`}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              strokeWidth={ringWidth}
              className="infographic-ring-track"
            />
          ))}

          {/* Active concentric rings */}
          <Ring
            cx={cx}
            cy={cy}
            r={radii[0]}
            strokeWidth={ringWidth}
            progress={stats.high.ratio}
            className="infographic-ring-high"
          />
          <Ring
            cx={cx}
            cy={cy}
            r={radii[1]}
            strokeWidth={ringWidth}
            progress={stats.medium.ratio}
            className="infographic-ring-medium"
          />
          <Ring
            cx={cx}
            cy={cy}
            r={radii[2]}
            strokeWidth={ringWidth}
            progress={stats.low.ratio}
            className="infographic-ring-low"
          />
        </svg>

        {/* Center score readout */}
        <div className="infographic-donut-center">
          <span className="infographic-donut-score">{score}</span>
          <span className="infographic-donut-max">/{maxScore}</span>
        </div>
      </div>

      {/* Legend & Summary Metrics */}
      <div className="infographic-donut-details">
        <div className="infographic-donut-legend">
          {SEV_ORDER.map((sev) => {
            const data = stats[sev]
            return (
              <div key={sev} className="infographic-legend-row">
                <span className={`infographic-dot dot-${sev}`} aria-hidden="true" />
                <span className="infographic-legend-name">{SEV_LABELS[sev]}</span>
                <span className="infographic-legend-val">
                  <strong>{data.pct}%</strong>
                  <small>({data.count})</small>
                </span>
              </div>
            )
          })}
        </div>

        <div className="infographic-severity-badge-row">
          <span className={`infographic-badge-pill tone-${severity}`}>
            {scoreFormatted}
          </span>
          {label && <span className="infographic-badge-sublabel">{label}</span>}
        </div>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// 2. InfographicPipelineSteps – Pipeline steps tracker (Parse → Rules → Score → Report)
// -----------------------------------------------------------------------
export function InfographicPipelineSteps() {
  const steps = [
    { num: '1', title: 'Parse', desc: 'Manifest & Dex' },
    { num: '2', title: 'Rules', desc: 'Static checks' },
    { num: '3', title: 'Score', desc: 'Exposure model' },
    { num: '4', title: 'Report', desc: 'Evidence verified' },
  ]

  return (
    <div className="infographic-pipeline-card" aria-label="Analysis pipeline steps">
      <div className="infographic-pipeline-track">
        {steps.map((step, idx) => (
          <div key={step.num} className="infographic-pipeline-step">
            <span className="infographic-pipeline-num">{step.num}</span>
            <div className="infographic-pipeline-info">
              <strong>{step.title}</strong>
              <small>{step.desc}</small>
            </div>
            {idx < steps.length - 1 && <span className="infographic-pipeline-arrow" aria-hidden="true">→</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// 3. InfographicFindingCard – Numbered finding card with horizontal progress bar
// -----------------------------------------------------------------------
export interface InfographicFindingCardProps {
  index: number
  finding: ReportFinding
  language: ReportLanguage
  onEvidence: (finding: ReportFinding) => void
}

export function InfographicFindingCard({
  index,
  finding,
  language,
  onEvidence,
}: InfographicFindingCardProps) {
  const pointsMax = 50
  const progressRatio = finding.points != null ? Math.min(finding.points / pointsMax, 1) : 0.2

  const explanation =
    finding.explanations[language] ??
    finding.explanations.en ??
    'No explanation is available for this language.'

  return (
    <div className={`infographic-finding-item sev-${finding.severity}`} role="article" aria-label={finding.title}>
      {/* Number Badge */}
      <div className="infographic-finding-col-num">
        <span className="infographic-number-circle" aria-hidden="true">
          {index + 1}
        </span>
      </div>

      {/* Content */}
      <div className="infographic-finding-content">
        <div className="infographic-finding-top">
          <div>
            <span className="eyebrow infographic-finding-rule">{finding.ruleId}</span>
            <h3 className="infographic-finding-title">{finding.title}</h3>
          </div>
          <span className={`infographic-sev-tag tag-${finding.severity}`}>
            {finding.severity.toUpperCase()}
          </span>
        </div>

        <p className="infographic-finding-summary">{finding.summary}</p>
        <p className="explanation">{explanation}</p>

        {/* Horizontal Progress Bar representing risk contribution */}
        {finding.points != null && (
          <div className="infographic-progress-wrapper" aria-label={`Risk weight: ${finding.points} points`}>
            <div className="infographic-progress-meta">
              <span className="infographic-progress-title">Risk contribution</span>
              <span className="infographic-progress-points">{finding.points} pts</span>
            </div>
            <div className="infographic-bar-track" aria-hidden="true">
              <div
                className={`infographic-bar-fill fill-${finding.severity}`}
                style={{ width: `${Math.round(progressRatio * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Footer with Claim Status and Evidence Action */}
        <div className="infographic-finding-actions">
          <span className={`infographic-claim-tag claim-${finding.claimStatus}`}>
            {finding.claimStatus.toUpperCase()}
          </span>

          <button
            type="button"
            className="text-button infographic-view-btn"
            onClick={() => onEvidence(finding)}
          >
            View evidence
          </button>
        </div>
      </div>
    </div>
  )
}
