import { useEffect, useState } from 'react'
import { Badge, Card, EmptyState, Header, PrimaryButton, ResponsiveGrid, UploadPlaceholder } from './components'
import './styles.css'

function AnalyzePage() {
  return <main className="page-content">
    <section className="hero-panel">
      <div><Badge tone="safe">INSPECT BEFORE YOU INSTALL</Badge><h2>Evidence-first Android static analysis.</h2><p>Understand what an APK declares before it reaches a device. The analyzer will inspect files without executing or installing them.</p></div>
      <Card><span className="eyebrow">DESIGN SYSTEM FOUNDATION</span><h2>What can this app access?</h2><p className="page-intro">A calm, reusable interface for future manifest and permission evidence.</p></Card>
    </section>
    <Card className="upload-placeholder"><span className="eyebrow">INPUT BAY</span><h3>Analyze an APK</h3><p className="page-intro">The upload workflow is not implemented in this frontend foundation.</p><UploadPlaceholder /><span className="demo-note">DEMO DATA: no APK is uploaded or analyzed here.</span></Card>
  </main>
}

function ReportPage() {
  return <main className="page-content"><span className="eyebrow">REPORT</span><h1 className="page-title">Analysis report</h1><Card className="report-placeholder"><EmptyState title="No report available" description="A report will appear here after a future static analysis run. This is a placeholder, not a security finding." action={<PrimaryButton type="button" onClick={() => { window.location.href = '/analyze' }}>Go to Analyze</PrimaryButton>} /></Card></main>
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname === '/report' ? '/report' : '/analyze')
  useEffect(() => { const onPopState = () => setPath(window.location.pathname === '/report' ? '/report' : '/analyze'); window.addEventListener('popstate', onPopState); return () => window.removeEventListener('popstate', onPopState) }, [])
  return <div className="app-shell"><div className="shell"><Header currentPath={path} />{path === '/report' ? <ReportPage /> : <AnalyzePage />}<ResponsiveGrid className="demo-note"><span>LIGHT THEME · REUSABLE UI FOUNDATION</span><span>STATIC ANALYSIS ONLY</span></ResponsiveGrid></div></div>
}
