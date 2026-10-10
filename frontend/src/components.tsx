import { useState, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from 'react'
import type { Theme } from './theme'
import logo from '../../assets/logo.png'
import alertIcon from '../../assets/apk-xray-icons/alert.svg'
import analyzeIcon from '../../assets/apk-xray-icons/analyze.svg'
import benchmarkIcon from '../../assets/apk-xray-icons/benchmark.svg'
import closeIcon from '../../assets/apk-xray-icons/close.svg'
import fileIcon from '../../assets/apk-xray-icons/file.svg'
import githubIcon from '../../assets/apk-xray-icons/github.svg'
import homeIcon from '../../assets/apk-xray-icons/home.svg'
import infoIcon from '../../assets/apk-xray-icons/info.svg'
import languageIcon from '../../assets/apk-xray-icons/language.svg'
import limitsIcon from '../../assets/apk-xray-icons/limits.svg'
import menuIcon from '../../assets/apk-xray-icons/menu.svg'
import mobileIcon from '../../assets/apk-xray-icons/mobile.svg'
import processIcon from '../../assets/apk-xray-icons/process.svg'
import reportIcon from '../../assets/apk-xray-icons/report.svg'
import rulesIcon from '../../assets/apk-xray-icons/rules.svg'
import scanIcon from '../../assets/apk-xray-icons/scan.svg'
import searchIcon from '../../assets/apk-xray-icons/search.svg'
import shieldCheckIcon from '../../assets/apk-xray-icons/shield-check.svg'
import uploadIcon from '../../assets/apk-xray-icons/upload.svg'
import './components.css'

const iconSources = {
  alert: alertIcon,
  analyze: analyzeIcon,
  benchmark: benchmarkIcon,
  close: closeIcon,
  file: fileIcon,
  github: githubIcon,
  home: homeIcon,
  info: infoIcon,
  language: languageIcon,
  limits: limitsIcon,
  menu: menuIcon,
  mobile: mobileIcon,
  process: processIcon,
  report: reportIcon,
  rules: rulesIcon,
  scan: scanIcon,
  search: searchIcon,
  shieldCheck: shieldCheckIcon,
  upload: uploadIcon,
} as const

export type IconName = keyof typeof iconSources

export function Icon({ name, label, size = 18 }: { name: IconName; label?: string; size?: number }) {
  return <img className="icon" src={iconSources[name]} alt={label ?? ''} aria-hidden={label ? undefined : true} width={size} height={size} />
}

const navigationItems = [
  { href: '/', label: 'Analyze', icon: 'analyze' as IconName },
  { href: '/report', label: 'Report', icon: 'report' as IconName },
  { href: '/about', label: 'About', icon: 'info' as IconName },
]

function NavigationLink({ href, label, icon, currentPath, collapsed }: {
  href: string
  label: string
  icon: IconName
  currentPath: string
  collapsed?: boolean
}) {
  const active = currentPath === href || (href === '/' && currentPath === '/analyze') || (href === '/report' && currentPath === '/report/sample')
  return <a className={`navigation-link${active ? ' is-active' : ''}`} href={href} aria-current={active ? 'page' : undefined} aria-label={collapsed ? label : undefined} title={collapsed ? label : undefined}>
    <Icon name={icon} />
    <span>{label}</span>
  </a>
}

export function NavigationLayout({ currentPath, theme, onThemeToggle, children }: {
  currentPath: string
  theme: Theme
  onThemeToggle: () => void
  children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  return <div className={`application-layout${collapsed ? ' sidebar-collapsed' : ''}`}>
    <aside className="sidebar" aria-label="Application navigation">
      <a className="sidebar-brand" href="/" aria-label="APK-XRAY dashboard">
        <img src={logo} alt="" className="brand-logo" />
        <span className="brand-wordmark">APK-XRAY</span>
      </a>
      <nav className="sidebar-navigation" aria-label="Primary">
        {navigationItems.map((item) => <NavigationLink key={item.href} {...item} currentPath={currentPath} collapsed={collapsed} />)}
      </nav>
      <button className="sidebar-toggle" type="button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} aria-pressed={collapsed}>
        <Icon name="menu" />
        <span>{collapsed ? 'Expand' : 'Collapse'}</span>
      </button>
    </aside>
    <div className="application-main">
      <header className="topbar" aria-label="Application controls">
        <a className="mobile-brand" href="/" aria-label="APK-XRAY dashboard"><img src={logo} alt="" className="brand-logo" /><span className="brand-wordmark">APK-XRAY</span></a>
        <div className="topbar-controls">
          <span className="header-status" aria-label="Analysis status">NO ANALYSIS YET</span>
          <button className="theme-toggle" type="button" onClick={onThemeToggle} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}>
            <svg className="theme-toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
              {theme === 'light' ? <path d="M12 3v2m0 14v2M5.64 5.64l1.42 1.42m9.9 9.9 1.4 1.4M3 12h2m14 0h2M5.64 18.36l1.42-1.42m9.9-9.9 1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" /> : <path d="M20.5 14.8A8 8 0 0 1 9.2 3.5 8 8 0 1 0 20.5 14.8Z" />}
            </svg>
            <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
          </button>
        </div>
      </header>
      <nav className="mobile-navigation" aria-label="Primary">
        {navigationItems.map((item) => <NavigationLink key={item.href} {...item} currentPath={currentPath} />)}
      </nav>
      {children}
    </div>
  </div>
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
    <Icon name="upload" />
    <div><strong>Select or drop an Android APK file</strong><span>Future upload workflow · static analysis only</span></div>
    <SecondaryButton type="button" disabled>Choose APK</SecondaryButton>
  </div>
}
