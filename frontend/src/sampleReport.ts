export type FindingSeverity = 'low' | 'medium' | 'high'

export interface SampleFinding {
  ruleId: string
  severity: FindingSeverity
  title: string
  summary: string
  evidence: string
}

export interface SampleReport {
  app: {
    name: string
    packageName: string
    version: string
    minSdk: number
  }
  exposureLevel: string
  score: {
    value: number
    label: string
    breakdown: string
  }
  findings: SampleFinding[]
  capabilityChain: string[]
  limitations: string[]
}

// Provisional frontend-only shape until the backend report schema is defined.
export const sampleReport: SampleReport = {
  app: {
    name: 'Example Lantern',
    packageName: 'org.example.lantern',
    version: '0.0.0-demo',
    minSdk: 26,
  },
  exposureLevel: 'Illustrative: moderate',
  score: {
    value: 42,
    label: 'Illustrative score',
    breakdown: 'Example weighting across fictional manifest evidence.',
  },
  findings: [
    {
      ruleId: 'APKX-DEMO-001',
      severity: 'medium',
      title: 'Example permission combination',
      summary: 'A fictional combination of declared permissions would merit review.',
      evidence: 'android.permission.READ_EXAMPLE and android.permission.ACCESS_EXAMPLE',
    },
    {
      ruleId: 'APKX-DEMO-002',
      severity: 'low',
      title: 'Example exported component',
      summary: 'A fictional exported component is shown for report-layout demonstration.',
      evidence: 'org.example.lantern.ExampleActivity exported=true',
    },
  ],
  capabilityChain: ['Declared permission', 'Example component', 'Deterministic rule', 'Evidence review'],
  limitations: [
    'This fixture is fictional and is not evidence about a real application.',
    'Static analysis cannot establish runtime behavior, user intent, or whether a capability was exercised.',
    'The score and exposure label are illustrative UI content, not a security assessment.',
  ],
}
