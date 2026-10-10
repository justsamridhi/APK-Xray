import { useEffect, useState } from 'react'
import { Badge, Card, EmptyState, Header, UploadPlaceholder } from './components'
import reportIcon from '../../assets/apk-xray-icons/report.svg'
import './styles.css'

function AnalyzePage() {
  return <main className="page-content">
    <section className="hero-panel">
      <div><Badge tone="safe">INSPECT BEFORE YOU INSTALL</Badge><h1>Evidence-first Android static analysis.</h1><p>Understand what an APK declares before it reaches a device. APKs will be inspected without being run or installed.</p></div>
      <Card><span className="eyebrow">DESIGN SYSTEM FOUNDATION</span><h2>What can this app access?</h2><p className="page-intro">A calm, reusable interface for future manifest and permission evidence.</p></Card>
    </section>
    <Card className="upload-placeholder"><span className="eyebrow">INPUT BAY</span><h2>Analyze an APK</h2><p className="page-intro">Upload is not available yet. This disabled placeholder will become the static analysis entry point.</p><UploadPlaceholder /><span className="demo-note">NO APK HAS BEEN UPLOADED OR ANALYZED.</span></Card>
  </main>
}

function ReportPage() {
  return <main className="page-content"><span className="eyebrow">REPORT</span><h1 className="page-title">Analysis report</h1><Card className="report-placeholder"><EmptyState icon={reportIcon} title="No report yet" description="A report will appear here after a future static analysis run. No security findings are available." action={<a className="button button-primary" href="/analyze">Go to Analyze</a>} /></Card></main>
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname === '/report' ? '/report' : '/analyze')
  useEffect(() => { const onPopState = () => setPath(window.location.pathname === '/report' ? '/report' : '/analyze'); window.addEventListener('popstate', onPopState); return () => window.removeEventListener('popstate', onPopState) }, [])
  return <div className="app-shell"><div className="shell"><Header currentPath={path} />{path === '/report' ? <ReportPage /> : <AnalyzePage />}<footer className="footer demo-note"><span>LIGHT THEME · REUSABLE UI FOUNDATION</span><span>STATIC ANALYSIS ONLY</span></footer></div></div>
}
