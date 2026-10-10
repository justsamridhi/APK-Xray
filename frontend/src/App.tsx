import { useCallback, useEffect, useRef, useState } from 'react'
import { Badge, Card, EmptyState, Icon, NavigationLayout, UploadPlaceholder, type IconName } from './components'
import reportIcon from '../../assets/apk-xray-icons/report.svg'
import { themeStorageKey, type Theme } from './theme'
import { sampleReport, type SampleFinding } from './sampleReport'
import './styles.css'

const validPaths: string[] = ['/', '/analyze', '/report', '/report/sample', '/about']

function getInitialTheme(): Theme {
  try {
    const saved = localStorage.getItem(themeStorageKey)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    // Storage may be unavailable in private browsing or a restricted environment.
  }
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function AnalyzePage() {
  return <main className="page-content">
    <section className="hero-panel">
      <div><Badge tone="safe">INSPECT BEFORE YOU INSTALL</Badge><h1>Evidence-first Android static analysis.</h1><p>Understand what an APK declares before it reaches a device. APKs will be inspected without being run or installed.</p></div>
      <Card><span className="eyebrow"><Icon name="shieldCheck" /> DESIGN SYSTEM FOUNDATION</span><h2>What can this app access?</h2><p className="page-intro">A calm, reusable interface for future manifest and permission evidence.</p></Card>
    </section>
    <Card className="upload-placeholder"><span className="eyebrow">INPUT BAY</span><h2>Analyze an APK</h2><p className="page-intro">Upload is not available yet. Backend integration is not configured, so no file is selected, uploaded, or executed.</p><UploadPlaceholder /><span className="demo-note">NO APK HAS BEEN UPLOADED OR ANALYZED.</span><a className="text-link" href="/report/sample">Explore a clearly labeled sample report</a></Card>
    <section className="pipeline-section" aria-labelledby="pipeline-heading"><div><span className="eyebrow">PLANNED PIPELINE</span><h2 id="pipeline-heading">From package to evidence</h2></div><div className="pipeline-grid">{([['upload', 'Upload'], ['file', 'Extract'], ['rules', 'Apply rules'], ['benchmark', 'Score'], ['info', 'Explain'], ['shieldCheck', 'Verify']] as [IconName, string][]).map(([icon, label]) => <div className="pipeline-step" key={label}><Icon name={icon} /><span>{label}</span><small>Planned</small></div>)}</div><p className="page-intro">No step runs in this frontend yet. A future backend will provide real progress and results.</p></section>
  </main>
}

function ReportPage() {
  return <main className="page-content"><span className="eyebrow">REPORT</span><h1 className="page-title">Analysis report</h1><Card className="report-placeholder"><EmptyState icon={reportIcon} title="No report yet" description="A report will appear here after a future static analysis run. No security findings are available." action={<div className="empty-actions"><a className="button button-primary" href="/">Go to Analyze</a><a className="text-link" href="/report/sample">View sample report</a></div>} /></Card></main>
}

function FindingCard({ finding, onEvidence, evidenceLabel, severityLabel }: { finding: SampleFinding; onEvidence: (trigger: HTMLButtonElement) => void; evidenceLabel: string; severityLabel: string }) {
  return <Card className="finding-card"><div className="finding-heading"><div><span className="eyebrow">{finding.ruleId}</span><h3>{finding.title}</h3></div><Badge tone={finding.severity === 'high' ? 'warning' : finding.severity === 'medium' ? 'scan' : 'safe'}>{severityLabel}</Badge></div><p>{finding.summary}</p><button className="text-button" type="button" onClick={(event) => onEvidence(event.currentTarget)}>{evidenceLabel}</button></Card>
}

function SampleReportPage() {
  const [language, setLanguage] = useState<'en' | 'hi'>('en')
  const [evidence, setEvidence] = useState<SampleFinding | null>(null)
  const evidenceDrawerRef = useRef<HTMLElement | null>(null)
  const evidenceTriggerRef = useRef<HTMLButtonElement | null>(null)
  const localizedFindings = language === 'en' ? sampleReport.findings : sampleReport.findings.map((finding, index) => ({
    ...finding,
    title: index === 0 ? 'उदाहरण अनुमति संयोजन' : 'उदाहरण एक्सपोर्ट किया गया घटक',
    summary: index === 0 ? 'घोषित अनुमतियों का एक काल्पनिक संयोजन समीक्षा योग्य होगा।' : 'रिपोर्ट लेआउट दिखाने के लिए एक काल्पनिक एक्सपोर्ट किया गया घटक दिखाया गया है।',
    evidence: index === 0 ? 'android.permission.READ_EXAMPLE और android.permission.ACCESS_EXAMPLE' : 'org.example.lantern.ExampleActivity exported=true',
  }))
  const copy = language === 'en' ? {
    reportType: 'ILLUSTRATIVE REPORT',
    intro: 'A fictional report fixture demonstrating the future report layout.',
    download: 'Download sample JSON',
    package: 'PACKAGE',
    version: 'VERSION',
    minSdk: 'MIN SDK',
    exposure: 'EXPOSURE',
    score: 'SCORE',
    findings: 'FICTIONAL FINDINGS',
    findingsTitle: 'Illustrative rule results',
    language: 'Explanation language',
    explanation: 'Can: show what the fixture declares. Could: identify evidence worth review. Cannot prove: runtime behavior or intent.',
    viewEvidence: 'View evidence',
    chain: 'CAPABILITY CHAIN',
    chainTitle: 'Example evidence path',
    limitations: 'LIMITATIONS',
    limitationsTitle: 'Read this fixture carefully',
    notVerified: 'EXPLANATION NOT VERIFIED',
    notRemoved: 'EXPLANATION NOT REMOVED',
    statesNote: 'These states demonstrate future report metadata; they are not claims about a real explanation.',
    evidence: 'EVIDENCE',
    closeEvidence: 'Close evidence',
    fixtureEvidence: 'Illustrative fixture evidence only.',
    sampleBanner: 'Sample data. This is not a real analysis.',
    severity: { low: 'LOW', medium: 'MEDIUM', high: 'HIGH' },
  } : {
    reportType: 'उदाहरण रिपोर्ट',
    intro: 'भविष्य की रिपोर्ट संरचना दिखाने वाली एक काल्पनिक रिपोर्ट।',
    download: 'उदाहरण JSON डाउनलोड करें',
    package: 'पैकेज',
    version: 'वर्ज़न',
    minSdk: 'न्यूनतम SDK',
    exposure: 'एक्सपोज़र',
    score: 'स्कोर',
    findings: 'काल्पनिक निष्कर्ष',
    findingsTitle: 'उदाहरण नियम परिणाम',
    language: 'व्याख्या की भाषा',
    explanation: 'कर सकता है: फ़िक्चर में घोषित चीज़ें दिखा सकता है। संभव है: समीक्षा योग्य साक्ष्य पहचान सकता है। साबित नहीं कर सकता: रनटाइम व्यवहार या इरादा।',
    viewEvidence: 'साक्ष्य देखें',
    chain: 'क्षमता श्रृंखला',
    chainTitle: 'उदाहरण साक्ष्य पथ',
    limitations: 'सीमाएँ',
    limitationsTitle: 'इस फ़िक्चर को ध्यान से पढ़ें',
    notVerified: 'व्याख्या सत्यापित नहीं है',
    notRemoved: 'व्याख्या हटाई नहीं गई है',
    statesNote: 'ये स्थितियाँ भविष्य के रिपोर्ट मेटाडेटा का उदाहरण हैं; ये किसी वास्तविक व्याख्या के दावे नहीं हैं।',
    evidence: 'साक्ष्य',
    closeEvidence: 'साक्ष्य बंद करें',
    fixtureEvidence: 'केवल उदाहरण फ़िक्चर का साक्ष्य।',
    sampleBanner: 'उदाहरण डेटा। यह वास्तविक विश्लेषण नहीं है।',
    severity: { low: 'कम', medium: 'मध्यम', high: 'अधिक' },
  }
  const closeEvidence = useCallback(() => {
    setEvidence(null)
    evidenceTriggerRef.current?.focus()
  }, [])
  useEffect(() => {
    if (!evidence) return
    const drawer = evidenceDrawerRef.current
    if (!drawer) return
    const getFocusable = () => Array.from(drawer.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter((element) => !element.hasAttribute('disabled'))
    const focusable = getFocusable()
    focusable[0]?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeEvidence()
        return
      }
      if (event.key !== 'Tab') return
      const currentFocusable = getFocusable()
      if (currentFocusable.length === 0) {
        event.preventDefault()
        return
      }
      const first = currentFocusable[0]
      const last = currentFocusable[currentFocusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [evidence, closeEvidence])
  const download = () => {
    const blob = new Blob([JSON.stringify(sampleReport, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'apk-xray-sample-report.json'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }
  return <main className="page-content sample-report">
    <div className="sample-banner" role="alert"><Icon name="info" /> <strong>{copy.sampleBanner}</strong></div>
    <div className="sample-heading"><div><span className="eyebrow">{copy.reportType}</span><h1 className="page-title">Example Lantern</h1><p className="page-intro">{copy.intro}</p></div><button className="button button-secondary" type="button" onClick={download}>{copy.download}</button></div>
    <Card><div className="metadata-grid"><div><span className="eyebrow">{copy.package}</span><strong>{sampleReport.app.packageName}</strong></div><div><span className="eyebrow">{copy.version}</span><strong>{sampleReport.app.version}</strong></div><div><span className="eyebrow">{copy.minSdk}</span><strong>{sampleReport.app.minSdk}</strong></div><div><span className="eyebrow">{copy.exposure}</span><strong>{language === 'en' ? sampleReport.exposureLevel : 'उदाहरण: मध्यम'}</strong></div><div><span className="eyebrow">{copy.score}</span><strong>{sampleReport.score.value} · {language === 'en' ? sampleReport.score.label : 'उदाहरण स्कोर'}</strong></div></div><p className="demo-note">{language === 'en' ? sampleReport.score.breakdown : 'काल्पनिक मेनिफेस्ट साक्ष्य पर आधारित उदाहरण भार।'}</p></Card>
    <section className="report-section"><div className="section-heading"><div><span className="eyebrow">{copy.findings}</span><h2>{copy.findingsTitle}</h2></div><div className="language-toggle" role="group" aria-label={copy.language}><button type="button" className={language === 'en' ? 'selected' : ''} onClick={() => setLanguage('en')}>English</button><button type="button" className={language === 'hi' ? 'selected' : ''} onClick={() => setLanguage('hi')}>हिन्दी</button></div></div><p className="page-intro">{copy.explanation}</p><div className="finding-grid">{localizedFindings.map((finding) => <FindingCard key={finding.ruleId} finding={finding} evidenceLabel={copy.viewEvidence} severityLabel={copy.severity[finding.severity]} onEvidence={(trigger) => { evidenceTriggerRef.current = trigger; setEvidence(finding) }} />)}</div></section>
    <section className="report-section"><span className="eyebrow">{copy.chain}</span><h2>{copy.chainTitle}</h2><div className="chain">{sampleReport.capabilityChain.map((step, index) => <span key={step}>{index + 1}. {language === 'en' ? step : ['घोषित अनुमति', 'उदाहरण घटक', 'नियतात्मक नियम', 'साक्ष्य समीक्षा'][index]}</span>)}</div></section>
    <section className="report-section limitations"><span className="eyebrow">{copy.limitations}</span><h2>{copy.limitationsTitle}</h2><ul>{(language === 'en' ? sampleReport.limitations : ['यह फ़िक्चर काल्पनिक है और किसी वास्तविक ऐप का साक्ष्य नहीं है।', 'स्थैतिक विश्लेषण रनटाइम व्यवहार, उपयोगकर्ता के इरादे या क्षमता के उपयोग को साबित नहीं कर सकता।', 'स्कोर और एक्सपोज़र लेबल उदाहरण UI सामग्री हैं, सुरक्षा आकलन नहीं।']).map((item) => <li key={item}>{item}</li>)}</ul><div className="state-badges"><Badge tone="warning">{copy.notVerified}</Badge><Badge tone="schema">{copy.notRemoved}</Badge></div><p className="demo-note">{copy.statesNote}</p></section>
    {evidence && <div className="evidence-backdrop" role="presentation" onClick={closeEvidence}><aside ref={evidenceDrawerRef} className="evidence-drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-title" onClick={(event) => event.stopPropagation()}><button className="drawer-close" type="button" aria-label={copy.closeEvidence} onClick={closeEvidence}><Icon name="close" /></button><span className="eyebrow">{copy.evidence}</span><h2 id="evidence-title">{evidence.ruleId}</h2><p>{evidence.evidence}</p><span className="demo-note">{copy.fixtureEvidence}</span></aside></div>}
  </main>
}

function AboutPage() {
  return <main className="page-content about-page"><span className="eyebrow">ABOUT APK-XRAY</span><h1 className="page-title">Inspect first. Explain carefully.</h1><p className="page-intro">APK-Xray is designed to examine Android APK declarations without executing or installing them. This frontend describes the intended product; the analyzer and backend are not connected yet.</p><section className="about-grid"><Card><Icon name="scan" /><h2>Static-analysis pipeline</h2><p>Upload, extract, apply deterministic rules, score, explain, and verify—once the backend exists.</p></Card><Card><Icon name="shieldCheck" /><h2>Product principles</h2><ul><li>Static only</li><li>Rules decide</li><li>Evidence or it does not appear</li><li>No unsupported intent claims</li><li>Minimal data</li><li>Openness</li></ul></Card><Card><Icon name="limits" /><h2>Privacy and limits</h2><p>The current frontend does not upload or retain APKs. Once implemented, privacy behavior must be documented by the actual backend.</p><p>Static analysis cannot establish runtime behavior, user intent, or that a finding is malware.</p></Card></section></main>
}

export default function App() {
  const [path, setPath] = useState(validPaths.includes(window.location.pathname) ? window.location.pathname : '/')
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  useEffect(() => { const onPopState = () => setPath(validPaths.includes(window.location.pathname) ? window.location.pathname : '/'); window.addEventListener('popstate', onPopState); return () => window.removeEventListener('popstate', onPopState) }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(themeStorageKey, theme)
    } catch {
      // The app remains usable when persistence is unavailable.
    }
  }, [theme])
  return <NavigationLayout currentPath={path} theme={theme} onThemeToggle={() => setTheme((current) => current === 'light' ? 'dark' : 'light')}><div className="shell">{path === '/report' ? <ReportPage /> : path === '/report/sample' ? <SampleReportPage /> : path === '/about' ? <AboutPage /> : <AnalyzePage />}<footer className="footer demo-note"><span>LIGHT / DARK THEME · REUSABLE UI FOUNDATION</span><span>STATIC ANALYSIS ONLY</span></footer></div></NavigationLayout>
}
