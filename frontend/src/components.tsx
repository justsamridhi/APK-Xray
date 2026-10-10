import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import logo from '../../assets/logo.png'
import analyzeIcon from '../../assets/apk-xray-icons/analyze.svg'
import reportIcon from '../../assets/apk-xray-icons/report.svg'
import uploadIcon from '../../assets/apk-xray-icons/upload.svg'
import './components.css'

export function Header({ currentPath }: { currentPath: string }) {
  return <header className="header" aria-label="Primary navigation">
    <a className="brand" href="/analyze" aria-label="APK X-ray home">
      <img src={logo} alt="APK X-ray" className="brand-logo" />
    </a>
    <nav className="nav-tabs">
      <a href="/analyze" aria-current={currentPath === '/analyze' ? 'page' : undefined}><img src={analyzeIcon} alt="" />Analyze</a>
      <a href="/report" aria-current={currentPath === '/report' ? 'page' : undefined}><img src={reportIcon} alt="" />Report</a>
    </nav>
    <span className="header-status" aria-label="Analysis status">NO ANALYSIS YET</span>
  </header>
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }
export function PrimaryButton({ children, className = '', ...props }: ButtonProps) {
  return <button className={`button button-primary ${className}`} {...props}>{children}</button>
}
export function SecondaryButton({ children, className = '', ...props }: ButtonProps) {
  return <button className={`button button-secondary ${className}`} {...props}>{children}</button>
}

export function Card({ children, className = '', ...props }: { children: ReactNode; className?: string } & HTMLAttributes<HTMLElement>) {
  return <section className={`card ${className}`} {...props}>{children}</section>
}

type BadgeTone = 'safe' | 'scan' | 'warning' | 'schema'
export function Badge({ children, tone = 'safe' }: { children: ReactNode; tone?: BadgeTone }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function LoadingSpinner({ label = 'Loading' }: { label?: string }) {
  return <span className="spinner-wrap" role="status"><span className="spinner" aria-hidden="true" />{label}</span>
}

export function EmptyState({ title, description, icon, action }: { title: string; description: string; icon?: string; action?: ReactNode }) {
  return <div className="empty-state">{icon && <img className="empty-icon" src={icon} alt="" /> }<h2>{title}</h2><p>{description}</p>{action}</div>
}

export function ResponsiveGrid({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`responsive-grid ${className}`}>{children}</div>
}

export function UploadPlaceholder() {
  return <div className="upload-row">
    <img src={uploadIcon} alt="" />
    <div><strong>Select or drop an Android APK file</strong><span>Future upload workflow · static analysis only</span></div>
    <SecondaryButton type="button" disabled>Choose APK</SecondaryButton>
  </div>
}
