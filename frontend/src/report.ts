export type ReportSeverity = 'low' | 'medium' | 'high'
export type ClaimStatus = 'verified' | 'removed' | 'unsupported' | 'unavailable'
export type ReportLanguage = 'en' | 'hi'

export interface ReportEvidence {
  id: string
  label: string
  snippet?: string
}

export interface ReportFinding {
  ruleId: string
  severity: ReportSeverity
  title: string
  summary: string
  evidence: ReportEvidence[]
  claimStatus: ClaimStatus
  points: number | null
  explanations: Partial<Record<ReportLanguage, string>>
}

export interface CapabilityChain {
  id: string
  label: string
  steps: Array<{ id: string; label: string; evidenceId?: string }>
}

export interface ReportData {
  app: {
    name: string
    packageName: string
    version: string
  }
  score: {
    value: number
    label: string
    severity: 'low' | 'moderate' | 'high' | 'very-high'
  }
  findings: ReportFinding[]
  capabilityChains: CapabilityChain[]
}

const severities = new Set<ReportSeverity>(['low', 'medium', 'high'])
const claimStatuses = new Set<ClaimStatus>(['verified', 'removed', 'unsupported', 'unavailable'])

function text(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function evidenceList(value: unknown): ReportEvidence[] {
  if (!Array.isArray(value)) return []
  return value.map((item, index) => {
    if (typeof item === 'string' && item.trim()) {
      return { id: `evidence-${index + 1}`, label: item }
    }

    if (!item || typeof item !== 'object') {
      return { id: `unavailable-${index + 1}`, label: 'Evidence unavailable' }
    }
    const candidate = item as Record<string, unknown>
    const id = text(candidate.id, '')
    return {
      id: id || `unavailable-${index + 1}`,
      label: text(candidate.label ?? candidate.type, 'Evidence unavailable'),
      snippet: typeof candidate.snippet === 'string' ? candidate.snippet : undefined,
    }
  })
}

function explanations(value: unknown): Partial<Record<ReportLanguage, string>> {
  if (!value || typeof value !== 'object') return {}
  const source = value as Record<string, unknown>
  return {
    en: typeof source.en === 'string' && source.en.trim() ? source.en : undefined,
    hi: typeof source.hi === 'string' && source.hi.trim() ? source.hi : undefined,
  }
}

function capabilityChains(value: unknown): CapabilityChain[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item, index) => {
    if (!item || typeof item !== 'object') return []
    const source = item as Record<string, unknown>
    if (!Array.isArray(source.steps)) return []
    const steps = source.steps.flatMap((step, stepIndex) => {
      if (typeof step === 'string') return [{ id: `${index + 1}-${stepIndex + 1}`, label: step }]
      if (!step || typeof step !== 'object') return []
      const candidate = step as Record<string, unknown>
      return [{ id: text(candidate.id, `${index + 1}-${stepIndex + 1}`), label: text(candidate.label, 'Unavailable step'), evidenceId: typeof candidate.evidenceId === 'string' ? candidate.evidenceId : undefined }]
    })
    return [{ id: text(source.id, `C${index + 1}`), label: text(source.label, `Capability chain ${index + 1}`), steps }]
  })
}

export function normalizeReport(value: unknown): ReportData | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const app = raw.app
  const score = raw.score
  if (!app || typeof app !== 'object' || !score || typeof score !== 'object' || !Array.isArray(raw.findings)) return null
  const rawApp = app as Record<string, unknown>
  const rawScore = score as Record<string, unknown>
  if (typeof rawScore.value !== 'number' || !Number.isFinite(rawScore.value)) return null
  const findings: ReportFinding[] = []
  for (const item of raw.findings) {
    if (!item || typeof item !== 'object') return null
    const finding = item as Record<string, unknown>
    const severity = finding.severity
    if (typeof finding.ruleId !== 'string' || !severities.has(severity as ReportSeverity)) return null
    const claimStatus = claimStatuses.has(finding.claimStatus as ClaimStatus) ? finding.claimStatus as ClaimStatus : 'unavailable'
    findings.push({
      ruleId: finding.ruleId,
      severity: severity as ReportSeverity,
      title: text(finding.title, 'Untitled finding'),
      summary: text(finding.summary, 'No summary available.'),
      evidence: evidenceList(finding.evidence),
      claimStatus,
      points: typeof finding.points === 'number' && Number.isFinite(finding.points) ? finding.points : null,
      explanations: explanations(finding.explanations),
    })
  }
  return {
    app: {
      name: text(rawApp.name, 'Unknown application'),
      packageName: text(rawApp.packageName, 'Package name unavailable'),
      version: text(rawApp.version, 'Version unavailable'),
    },
    score: {
      value: rawScore.value,
      label: text(rawScore.label, 'Unclassified'),
      severity: rawScore.severity === 'low' || rawScore.severity === 'moderate' || rawScore.severity === 'high' || rawScore.severity === 'very-high' ? rawScore.severity : 'moderate',
    },
    findings,
    capabilityChains: capabilityChains(raw.capabilityChains),
  }
}
