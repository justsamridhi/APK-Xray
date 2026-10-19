
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react'

import { Badge, Card, EmptyState, Icon, LoadingSpinner, NavigationLayout, PrimaryButton, SecondaryButton, type IconName } from './ui-components'

import reportIcon from '../../assets/apk-xray-icons/report.svg'

import { themeStorageKey, type Theme } from './theme'

import { sampleReport, type SampleFinding } from './sampleReport'

import { normalizeReport, type ReportData, type ReportFinding, type ReportLanguage } from './report'

import { API_BASE } from './config'
import { maxApkSize, upload, getReport, UploadError } from './api'

import './styles.css'

const validPaths: string[] = ['/', '/analyze', '/report', '/report/sample', '/about']

function isValidPath(path: string): boolean {
  return validPaths.includes(path) || /^\/report\/[^/]+$/.test(path)
}

const apkMimeTypes = new Set(['application/vnd.android.package-archive', 'application/octet-stream', ''])

type UploadState = 'idle' | 'ready' | 'uploading' | 'error'

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function validateApk(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.apk') || !apkMimeTypes.has(file.type)) {
    return 'Choose an Android APK file. Other file types are not accepted.'
  }
  if (file.size === 0) return 'This APK is empty. Choose a non-empty APK file.'
  if (file.size > maxApkSize) {
    return 'This APK is larger than the 50 MB limit.'
  }
  return null
}

function getInitialTheme(): Theme {
  try {
    const saved = localStorage.getItem(themeStorageKey)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    // Storage may be unavailable in private browsing or a restricted environment.
  }
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const typewriterTargets = [
  '"fake_traffic_challan.apk"',
  '"gas_bill_kyc_update.apk"',
  '"parcel_delivery_duty.apk"',
  '"govt_subsidy_scheme.apk"',
  '"banking_support_patch.apk"',
]

function TypewriterTarget() {
  const [text, setText] = useState('')

  useEffect(() => {
    let phraseIndex = 0
    let characterIndex = 0
    let deleting = false
    let timer: number | undefined

    const tick = () => {
      const phrase = typewriterTargets[phraseIndex]
      characterIndex += deleting ? -1 : 1
      setText(phrase.slice(0, characterIndex))

      if (!deleting && characterIndex === phrase.length) {
        deleting = true
        timer = window.setTimeout(tick, 1600)
      } else if (deleting && characterIndex === 0) {
        deleting = false
        phraseIndex = (phraseIndex + 1) % typewriterTargets.length
        timer = window.setTimeout(tick, 400)
      } else {
        timer = window.setTimeout(tick, deleting ? 45 : 85)
      }
    }

    tick()
    return () => { if (timer !== undefined) window.clearTimeout(timer) }
  }, [])

  return <div className="typewriter-box" aria-label={`Example APK target: ${text || typewriterTargets[0]}`}>
    <span className="typewriter-prefix">$ detect_threats --target</span>
    <span className="typewriter-text" aria-hidden="true">{text}</span><span className="cursor" aria-hidden="true" />
  </div>
}

function AnalyzePage({ onReport }: { onReport: (report: ReportData) => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [state, setState] = useState<UploadState>('idle')
  const [isDragging, setIsDragging] = useState(false)
  const [controller, setController] = useState<AbortController | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  const requestIdRef = useRef(0)

  const selectFile = (candidate: File | undefined) => {
    if (!candidate) return
    const validationError = validateApk(candidate)
    setError(validationError)
    setFile(validationError ? null : candidate)
    setState(validationError ? 'error' : 'ready')
  }

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    selectFile(event.target.files?.[0])
    event.target.value = ''
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    selectFile(event.dataTransfer.files[0])
  }

  const handleDropzoneKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      fileInputRef.current?.click()
    }
  }

  const uploadFile = async () => {
    if (!file || state === 'uploading') return
    setState('uploading')
    setError(null)
    const requestId = ++requestIdRef.current
    const requestController = new AbortController()
    setController(requestController)
    const timeout = window.setTimeout(() => requestController.abort(new DOMException('Timed out', 'TimeoutError')), 90_000)

    try {
      const result = await upload(file, requestController.signal)
      if (requestIdRef.current !== requestId) return

      const reportId = result.raw.reportId
      if (typeof reportId !== 'string' || !reportId.trim()) {
        throw new Error('The analysis returned no report ID.')
      }

      onReport(result)
      window.history.pushState({}, '', `/report/${encodeURIComponent(reportId)}`)
      window.dispatchEvent(new PopStateEvent('popstate'))
    } catch (uploadError) {
      if (requestIdRef.current !== requestId) return
      setState('error')
      setError(uploadError instanceof UploadError ? uploadError.message : 'The upload could not be completed. Try again.')
    } finally {
      window.clearTimeout(timeout)
      if (requestIdRef.current === requestId) {
        setController(null)
        if (resultRef.current) resultRef.current.focus()
      }
    }
  }

  return <main className="page-content">
    <section className="hero-panel">
      <div><Badge tone="safe">INSPECT BEFORE YOU INSTALL</Badge><h1>Evidence-first Android static analysis.</h1><TypewriterTarget /><p>Understand what an APK declares before it reaches a device. APKs will be inspected without being run or installed.</p></div>
      <Card><span className="eyebrow"><Icon name="shieldCheck" /> EVIDENCE REVIEW</span><h2>What does this APK declare?</h2><p className="page-intro">Review permissions and exported components before installing. Findings are deterministic and linked to manifest evidence.</p></Card>
    </section>
    <Card className="upload-placeholder scanner-deck">
      <div className="scanner-deck-header"><span className="radar-dot" aria-hidden="true" /><span className="eyebrow">LIVE STATIC INSPECTION</span><span className="scanner-deck-status">READY</span></div>
      <span className="eyebrow">INPUT BAY</span>
      <h2>Analyze an APK</h2>
      <p className="page-intro">Select an APK to send it for static analysis. The file is uploaded only; it is never executed or installed.</p>
      <input ref={fileInputRef} className="visually-hidden" type="file" accept=".apk,application/vnd.android.package-archive" onChange={handleFileInput} aria-label="Choose APK file" />
      <div
        className={`upload-dropzone${isDragging ? ' is-dragging' : ''}${error ? ' has-error' : ''}`}
        role="button"
        tabIndex={state === 'uploading' ? -1 : 0}
        aria-label="Drop an APK file here or press Enter to choose one"
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={handleDropzoneKeyDown}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true) }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => { if (event.currentTarget === event.target) setIsDragging(false) }}
        onDrop={handleDrop}
      >
        <Icon name="upload" size={32} />
        <strong>{file ? file.name : 'Select or drop an Android APK file'}</strong>
        <span>{file ? `${formatFileSize(file.size)} · Ready to upload` : 'APK files only · Maximum size 50 MB'}</span>
      </div>
      {error && <p className="upload-error" role="alert"><Icon name="alert" />{error}</p>}
      {file && !error && <p className="upload-success" role="status"><Icon name="shieldCheck" />File validated and ready for static analysis.</p>}
      {state === 'uploading' && <div ref={resultRef} tabIndex={-1}><LoadingSpinner label="Analyzing APK with the static backend… (free-tier servers may take 30-60s to wake up)" /></div>}
      <div className="upload-actions">
        <SecondaryButton type="button" onClick={() => fileInputRef.current?.click()} disabled={state === 'uploading'}>Choose APK</SecondaryButton>
        <PrimaryButton type="button" onClick={uploadFile} disabled={!file || state === 'uploading'}>{state === 'uploading' ? 'Analyzing…' : 'Start analysis'}</PrimaryButton>
        {state === 'uploading' && <SecondaryButton type="button" onClick={() => controller?.abort()} aria-label="Cancel analysis">Cancel analysis</SecondaryButton>}
        <span className="demo-note">NO APK IS EXECUTED.</span>
      </div>
      <a className="text-link" href="/report/sample">Explore a clearly labeled sample report</a>
    </Card>
    <section className="pipeline-section" aria-labelledby="pipeline-heading"><div><span className="eyebrow">STATIC PIPELINE</span><h2 id="pipeline-heading">From package to evidence</h2></div><div className="pipeline-grid">{([['upload', 'Receive APK'], ['file', 'Read manifest'], ['rules', 'Apply rules'], ['benchmark', 'Calculate score'], ['info', 'Explain evidence'], ['shieldCheck', 'Validate report']] as [IconName, string][]).map(([icon, label]) => <div className="pipeline-step" key={label}><Icon name={icon} /><span>{label}</span><small>Backend</small></div>)}</div><p className="page-intro">The backend reads declarations with Androguard, calculates the score deterministically, and never installs or executes the APK.</p></section>
  </main>
}

function findingTone(severity: ReportFinding['severity']) {
  return severity === 'high' ? 'warning' : severity === 'medium' ? 'scan' : 'safe'
}

function ReportEvidenceDrawer({ finding, onClose }: { finding: ReportFinding; onClose: () => void }) {
  const drawerRef = useRef<HTMLElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const drawer = drawerRef.current
    const getFocusable = () => drawer ? Array.from(drawer.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter((element) => !element.hasAttribute('disabled')) : []
    getFocusable()[0]?.focus()
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const focusable = getFocusable()
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previouslyFocusedRef.current?.focus()
    }
  }, [onClose])

  return <div className="evidence-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <aside ref={drawerRef} className="evidence-drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-heading">
      <button className="drawer-close" type="button" onClick={onClose} aria-label="Close evidence"><Icon name="close" /></button>
      <span className="eyebrow">EVIDENCE</span>
      <h2 id="evidence-heading">{finding.ruleId}</h2>
      <p>{finding.summary}</p>
      <div className="evidence-list">
        {finding.evidence.length === 0 ? <p className="evidence-unavailable">Evidence unavailable</p> : finding.evidence.map((evidence) => <article className="evidence-item" key={evidence.id}><strong>{evidence.id}</strong><span>{evidence.label}</span>{evidence.snippet && <code>{evidence.snippet}</code>}</article>)}
      </div>
    </aside>
  </div>
}

function ReportContent({ report }: { report: ReportData }) {
  const [evidenceFinding, setEvidenceFinding] = useState<ReportFinding | null>(null)
  const [language, setLanguage] = useState<ReportLanguage>('en')
  const closeEvidence = useCallback(() => setEvidenceFinding(null), [])
  const scoreTone = report.score.severity === 'high' || report.score.severity === 'very-high' ? 'warning' : report.score.severity === 'moderate' ? 'scan' : 'safe'
  const scoreLabel = report.score.severity.replace('-', ' ').toUpperCase()
  const evidenceForFinding = (finding: ReportFinding) => setEvidenceFinding(finding)

  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report.raw, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${report.app.packageName}-apk-xray-report.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  return <><div className="report-summary"><div><span className="eyebrow">ANALYSIS REPORT</span><h1 className="page-title">{report.app.name}</h1><p className="page-intro">{report.app.packageName} · version {report.app.version}</p>{report.ai && <p className="page-intro" role="status"><Badge tone={report.ai.status === 'verified' ? 'safe' : report.ai.status === 'error' ? 'warning' : 'schema'}>{report.ai.status === 'verified' ? 'AI VERIFIED' : report.ai.status === 'error' ? 'AI ERROR' : 'AI UNAVAILABLE'}</Badge> {report.ai.message}</p>}</div><div className="report-score"><span className="eyebrow">EXPOSURE SCORE</span><strong>{report.score.value}</strong><Badge tone={scoreTone}>{scoreLabel}</Badge><span className="score-label">{report.score.label}</span><button type="button" className="text-button" onClick={download}>Download report JSON</button></div></div>
    <section className="report-section" aria-labelledby="breakdown-heading"><div className="section-heading"><div><span className="eyebrow">DETERMINISTIC SCORING</span><h2 id="breakdown-heading">Score breakdown</h2></div></div><Card className="breakdown-card"><table className="breakdown-table"><caption className="visually-hidden">Rule contributions to the backend-provided exposure score</caption><thead><tr><th scope="col">Rule</th><th scope="col">Contribution</th></tr></thead><tbody>{report.findings.filter((finding) => finding.points !== null).map((finding) => <tr key={finding.ruleId}><th scope="row">{finding.ruleId}</th><td>{finding.points} points</td></tr>)}</tbody></table>{report.findings.every((finding) => finding.points === null) && <p className="page-intro">The backend did not provide rule contributions for this report.</p>}</Card></section>
    <section className="report-section" aria-labelledby="findings-heading"><div className="section-heading"><div><span className="eyebrow">FINDINGS</span><h2 id="findings-heading">{report.findings.length ? `${report.findings.length} results` : 'No findings'}</h2></div><div className="language-toggle" role="group" aria-label="Explanation language"><button type="button" className={language === 'en' ? 'selected' : ''} onClick={() => setLanguage('en')}>English</button><button type="button" className={language === 'hi' ? 'selected' : ''} onClick={() => setLanguage('hi')}>हिन्दी</button></div></div>{report.findings.length ? <div className="finding-grid">{report.findings.map((finding) => <Card className="finding-card" key={finding.ruleId}><div className="finding-heading"><div><span className="eyebrow">{finding.ruleId}</span><h3>{finding.title}</h3></div><Badge tone={findingTone(finding.severity)}>{finding.severity.toUpperCase()}</Badge></div><p>{finding.summary}</p><p className="explanation">{finding.explanations[language] ?? finding.explanations.en ?? 'No explanation is available for this language.'}</p><div className="state-badges"><Badge tone={finding.claimStatus === 'verified' ? 'safe' : finding.claimStatus === 'removed' ? 'warning' : 'schema'}>{finding.claimStatus.toUpperCase()}</Badge></div><button className="text-button" type="button" onClick={() => evidenceForFinding(finding)}>View evidence</button></Card>)}</div> : <Card className="report-placeholder"><EmptyState title="No findings reported" description="The analysis completed without reportable findings." /></Card>}</section>
    {report.capabilityChains.length > 0 && <section className="report-section" aria-labelledby="chains-heading"><div><span className="eyebrow">CAPABILITY CHAINS</span><h2 id="chains-heading">Evidence paths</h2></div><div className="chain-list">{report.capabilityChains.map((chain) => <Card className="chain-card" key={chain.id}><h3>{chain.id} · {chain.label}</h3><div className="chain">{chain.steps.map((step) => <button type="button" className="chain-step" key={step.id} onClick={() => { const finding = report.findings.find((candidate) => candidate.evidence.some((evidence) => evidence.id === step.evidenceId)); if (finding) evidenceForFinding(finding) }} disabled={!step.evidenceId}>{step.label}{step.evidenceId && <small>{step.evidenceId}</small>}</button>)}</div></Card>)}</div></section>}
    <section className="report-section limitations" aria-labelledby="limitations-heading"><span className="eyebrow">LIMITATIONS</span><h2 id="limitations-heading">What this report cannot prove</h2><ul><li>Static declarations do not prove runtime behavior or how permissions are used.</li><li>A finding is not proof that an app is malware or unsafe.</li><li>The deterministic score is an exposure heuristic, not a security guarantee.</li></ul></section>
    {evidenceFinding && <ReportEvidenceDrawer finding={evidenceFinding} onClose={closeEvidence} />}
  </>
}

function ReportPage({
  activeReport,
  onReport,
}: {
  activeReport: ReportData | null
  onReport: (report: ReportData) => void
}) {
  const [status, setStatus] = useState<'loading' | 'empty' | 'ready' | 'error'>('loading')
  const [report, setReport] = useState<ReportData | null>(null)
  const pathname = window.location.pathname
  const encodedReportId = pathname.startsWith('/report/') ? pathname.slice('/report/'.length) : ''

  let reportId: string | null = null
  if (encodedReportId) {
    try {
      reportId = decodeURIComponent(encodedReportId)
    } catch {
      reportId = null
    }
  }

  useEffect(() => {
    let active = true

    if (activeReport && (!reportId || activeReport.raw.reportId === reportId)) {
      setReport(activeReport)
      setStatus('ready')
      return () => { active = false }
    }

    if (reportId) {
      setReport(null)
      setStatus('loading')

      getReport(reportId)
        .then((result) => {
          if (!active) return
          if (result.raw.reportId !== reportId) {
            throw new Error('The returned report ID does not match the requested report.')
          }
          setReport(result)
          setStatus('ready')
          onReport(result)
        })
        .catch(() => {
          if (!active) return
          setReport(null)
          setStatus('error')
        })

      return () => { active = false }
    }

    setReport(null)
    setStatus('loading')

    fetch(import.meta.env.VITE_API_REPORT_URL ?? `${API_BASE}/api/report`)
      .then(async (response) => {
        if (response.status === 404 || response.status === 400) return null
        if (!response.ok) {
          const errorText = await response.text().catch(() => '')
          console.error(`[API Report Error] HTTP ${response.status}:`, errorText)
          throw new Error(`Report request failed with status ${response.status}.`)
        }
        let payload: unknown
        try {
          payload = await response.json()
        } catch {
          console.error(`[API Report Error] HTTP ${response.status}: Failed to parse JSON response.`)
          throw new Error('The report response was not valid JSON.')
        }
        const result = normalizeReport(payload)
        if (!result) throw new Error('The report was malformed.')
        return result
      })
      .then((result) => {
        if (!active) return
        if (!result) {
          setStatus('empty')
        } else {
          setReport(result)
          setStatus('ready')
          onReport(result)
        }
      })
      .catch((err) => {
        if (!active) return
        console.error('[API Report Error]:', err)
        setReport(null)
        setStatus('error')
      })

    return () => { active = false }
  }, [reportId, activeReport, onReport])

  if (status === 'loading') return <main className="page-content"><span className="eyebrow">REPORT</span><h1 className="page-title">Analysis report</h1><Card className="report-placeholder"><LoadingSpinner label="Loading report…" /></Card></main>

  if (status === 'error') return <main className="page-content"><span className="eyebrow">REPORT</span><h1 className="page-title">Analysis report</h1><Card className="report-placeholder"><EmptyState title="Report unavailable" description="The saved report could not be loaded. It may not exist or the analysis service may be unavailable." action={<a className="button button-primary" href="/">Return to Analyze</a>} /></Card></main>

  if (status === 'empty' || !report) return <main className="page-content"><span className="eyebrow">REPORT</span><h1 className="page-title">Analysis report</h1><Card className="report-placeholder"><EmptyState icon={reportIcon} title="No report yet" description="Upload an APK to generate a report, or explore the clearly labeled sample report." action={<div className="empty-actions"><a className="button button-primary" href="/">Go to Analyze</a><a className="text-link" href="/report/sample">View sample report</a></div>} /></Card></main>

  return <main className="page-content"><ReportContent report={report} /></main>
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
  return <main className="page-content about-page"><span className="eyebrow">ABOUT APK-XRAY</span><h1 className="page-title">Inspect first. Explain carefully.</h1><p className="page-intro">APK-Xray connects this interface to a static FastAPI analysis backend. APK declarations are inspected without installing or executing the package.</p><section className="about-grid"><Card><Icon name="scan" /><h2>Static-analysis pipeline</h2><p>Upload, read the manifest, apply deterministic rules, calculate exposure, optionally explain supplied evidence, and validate the report.</p></Card><Card><Icon name="shieldCheck" /><h2>Product principles</h2><ul><li>Static only</li><li>Rules decide</li><li>Evidence or it does not appear</li><li>No unsupported intent claims</li><li>Minimal data</li><li>Clear AI status</li></ul></Card><Card><Icon name="limits" /><h2>Privacy and limits</h2><p>Uploaded APKs are handled by the backend for static parsing and are not installed or executed.</p><p>Static analysis cannot establish runtime behavior, user intent, malware status, or complete safety.</p></Card></section></main>
}

export default function App() {
  const [path, setPath] = useState(
    isValidPath(window.location.pathname) ? window.location.pathname : '/',
  )
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  const [report, setReport] = useState<ReportData | null>(null)

  useEffect(() => {
    const onPopState = () => {
      setPath(isValidPath(window.location.pathname) ? window.location.pathname : '/')
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(themeStorageKey, theme)
    } catch {
      // The app remains usable when persistence is unavailable.
    }
  }, [theme])

  useEffect(() => {
    const updateAmbientGlow = (event: MouseEvent) => {
      document.documentElement.style.setProperty('--mouse-x', `${(event.clientX / window.innerWidth) * 100}%`)
      document.documentElement.style.setProperty('--mouse-y', `${(event.clientY / window.innerHeight) * 100}%`)
    }
    window.addEventListener('mousemove', updateAmbientGlow, { passive: true })
    return () => window.removeEventListener('mousemove', updateAmbientGlow)
  }, [])

  return <><div className='ambient-glow' /><div className='grid-bg' /><div className='scanline' /><div className='bg-radial' /><div className='bg-radial-2' /><NavigationLayout currentPath={path} theme={theme} onThemeToggle={() => setTheme((current) => current === 'light' ? 'dark' : 'light')}><div className="shell">{path === '/report/sample' ? <SampleReportPage /> : path === '/report' || path.startsWith('/report/') ? <ReportPage activeReport={report} onReport={setReport} /> : path === '/about' ? <AboutPage /> : <AnalyzePage onReport={setReport} />}<footer className="footer demo-note"><span>STATIC ANALYSIS · EVIDENCE REVIEW</span><span>APKS ARE NEVER EXECUTED</span></footer></div></NavigationLayout></>
}
