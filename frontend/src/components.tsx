import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import type { Theme } from './theme'
import logo from '../../assets/logo.png'
import analyzeIcon from '../../assets/apk-xray-icons/analyze.svg'
import reportIcon from '../../assets/apk-xray-icons/report.svg'
import uploadIcon from '../../assets/apk-xray-icons/upload.svg'
import './components.css'

export function Header({ currentPath, theme, onThemeToggle }: { currentPath: string; theme: Theme; onThemeToggle: () => void }) {
  return <header className="header" aria-label="Primary navigation">
    <a className="brand" href="/analyze" aria-label="APK X-ray home">
      <img src={logo} alt="APK X-ray" className="brand-logo" />
    </a>
    <nav className="nav-tabs">
      <a href="/analyze" aria-current={currentPath === '/analyze' ? 'page' : undefined}><img src={analyzeIcon} alt="" />Analyze</a>
      <a href="/report" aria-current={currentPath === '/report' ? 'page' : undefined}><img src={reportIcon} alt="" />Report</a>
    </nav>
    <span className="header-status" aria-label="Analysis status">NO ANALYSIS YET</span>
    <button className="theme-toggle" type="button" onClick={onThemeToggle} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}>
      <svg className="theme-toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
        {theme === 'light' ? <path d="M12 3v2m0 14v2M5.64 5.64l1.42 1.42m9.9 9.9 1.4 1.4M3 12h2m14 0h2M5.64 18.36l1.42-1.42m9.9-9.9 1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" /> : <path d="M20.5 14.8A8 8 0 0 1 9.2 3.5 8 8 0 1 0 20.5 14.8Z" />}
      </svg>
      <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
    </button>
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
