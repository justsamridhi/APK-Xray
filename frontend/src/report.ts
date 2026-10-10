export type ReportSeverity = 'low' | 'medium' | 'high'
export type ClaimStatus = 'verified' | 'removed' | 'unsupported' | 'unavailable'

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
  }
  findings: ReportFinding[]
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
    })
  }
  return {
    app: {
      name: text(rawApp.name, 'Unknown application'),
      packageName: text(rawApp.packageName, 'Package name unavailable'),
      version: text(rawApp.version, 'Version unavailable'),
    },
    score: { value: rawScore.value, label: text(rawScore.label, 'Unclassified') },
    findings,
  }
}
