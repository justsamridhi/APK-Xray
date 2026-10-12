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
  raw: Record<string, unknown>
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
  ai?: {
    status: 'verified' | 'unavailable' | 'error'
    provider: string
    message: string
  }
}

const severities = new Set<ReportSeverity>(['low', 'medium', 'high'])
const claimStatuses = new Set<ClaimStatus>(['verified', 'removed', 'unsupported', 'unavailable'])

function text(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function evidenceList(value: unknown): ReportEvidence[] | null {
  if (!Array.isArray(value)) return null
  const evidence: ReportEvidence[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') return null
    const candidate = item as Record<string, unknown>
    if (typeof candidate.id !== 'string' || !candidate.id.trim() || typeof candidate.label !== 'string' || !candidate.label.trim() || !['available', 'unavailable'].includes(candidate.availability as string)) return null
    evidence.push({
      id: candidate.id,
      label: candidate.label,
      snippet: typeof candidate.snippet === 'string' ? candidate.snippet : undefined,
    })
  }
  return evidence
}

function explanations(value: unknown): Partial<Record<ReportLanguage, string>> {
  if (!value || typeof value !== 'object') return {}
  const source = value as Record<string, unknown>
  return {
    en: typeof source.en === 'string' && source.en.trim() ? source.en : undefined,
    hi: typeof source.hi === 'string' && source.hi.trim() ? source.hi : undefined,
  }
}

function isLocalizedText(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const source = value as Record<string, unknown>
  return typeof source.en === 'string' && source.en.trim().length > 0
    && typeof source.hi === 'string' && source.hi.trim().length > 0
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
  if (raw.schemaVersion !== '1.0' || typeof raw.reportId !== 'string' || typeof raw.generatedAt !== 'string') return null
  if (typeof rawApp.packageName !== 'string' || !rawApp.packageName.trim() || !/^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$/.test(rawApp.packageName) || !('minSdk' in rawApp) || !('targetSdk' in rawApp) || !Array.isArray(rawApp.permissions) || !Array.isArray(rawApp.components)) return null
  if (typeof rawScore.value !== 'number' || !Number.isFinite(rawScore.value) || rawScore.value < 0 || rawScore.value > 100) return null
  if (!Array.isArray(rawScore.breakdown) || !Array.isArray(raw.claims) || !['low', 'moderate', 'high', 'very-high'].includes(rawScore.severity as string)) return null
  if (raw.claims.some((claim) => !claim || typeof claim !== 'object' || typeof (claim as Record<string, unknown>).id !== 'string' || !isLocalizedText((claim as Record<string, unknown>).text) || !['Can', 'Could', 'Cannot Prove'].includes((claim as Record<string, unknown>).classification as string) || !Array.isArray((claim as Record<string, unknown>).evidenceIds) || !['verified', 'removed', 'unsupported', 'unavailable'].includes((claim as Record<string, unknown>).status as string))) return null
  const findings: ReportFinding[] = []
  for (const item of raw.findings) {
    if (!item || typeof item !== 'object') return null
    const finding = item as Record<string, unknown>
    const severity = finding.severity
    if (typeof finding.ruleId !== 'string' || !severities.has(severity as ReportSeverity) || typeof finding.title !== 'string' || typeof finding.summary !== 'string' || !Array.isArray(finding.evidence) || !claimStatuses.has(finding.claimStatus as ClaimStatus) || !('points' in finding) || !('explanations' in finding)) return null
    if (!finding.explanations || typeof finding.explanations !== 'object') return null
    const evidence = evidenceList(finding.evidence)
    if (!evidence) return null
    const claimStatus = claimStatuses.has(finding.claimStatus as ClaimStatus) ? finding.claimStatus as ClaimStatus : 'unavailable'
    findings.push({
      ruleId: finding.ruleId,
      severity: severity as ReportSeverity,
      title: text(finding.title, 'Untitled finding'),
      summary: text(finding.summary, 'No summary available.'),
      evidence,
      claimStatus,
      points: finding.points === null ? null : typeof finding.points === 'number' && Number.isFinite(finding.points) ? finding.points : null,
      explanations: explanations(finding.explanations),
    })
  }
  return {
    raw,
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
    ai: raw.ai && typeof raw.ai === 'object' && ['verified', 'unavailable', 'error'].includes((raw.ai as Record<string, unknown>).status as string)
      ? {
          status: (raw.ai as Record<string, 'verified' | 'unavailable' | 'error'>).status,
          provider: text((raw.ai as Record<string, unknown>).provider, 'AI'),
          message: text((raw.ai as Record<string, unknown>).message, 'AI explanation status unavailable.'),
        }
      : undefined,
  }
}
