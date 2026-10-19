import React, { useEffect } from 'react'
import type { ReportLanguage } from '../report'

export interface UX4GLanguageSelectorProps {
  currentLanguage: ReportLanguage
  onLanguageChange: (language: ReportLanguage) => void
  label?: string
  className?: string
  showBadge?: boolean
}

/**
 * UX4G Multilingual Language Selector Component
 * Conforms to Government of India UX4G Design System guidelines:
 * - Native language scripts (Autonyms: English, हिन्दी)
 * - Dynamic document.documentElement.lang synchronization (WCAG 2.1 AA / GIGW compliance)
 * - Accessible ARIA attributes and keyboard operability
 * - UX4G indicator and tokens
 */
export function UX4GLanguageSelector({
  currentLanguage,
  onLanguageChange,
  label = 'Explanation language',
  className = '',
  showBadge = true,
}: UX4GLanguageSelectorProps) {
  // UX4G Accessibility Standard: dynamically update document.documentElement.lang
  useEffect(() => {
    document.documentElement.lang = currentLanguage
  }, [currentLanguage])

  return (
    <div className={`ux4g-multilingual-wrapper ${className}`.trim()}>
      <div
        className="ux4g-language-selector language-toggle"
        role="group"
        aria-label={label}
        data-ux4g="multilingual-support"
      >
        {showBadge && (
          <span className="ux4g-lang-indicator" title="UX4G Multilingual Support">
            <svg
              className="ux4g-lang-icon"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <span className="ux4g-badge-text">UX4G</span>
          </span>
        )}

        <button
          type="button"
          className={`ux4g-lang-btn ${currentLanguage === 'en' ? 'selected active' : ''}`}
          onClick={() => onLanguageChange('en')}
          aria-pressed={currentLanguage === 'en'}
          lang="en"
        >
          English
        </button>

        <button
          type="button"
          className={`ux4g-lang-btn ${currentLanguage === 'hi' ? 'selected active' : ''}`}
          onClick={() => onLanguageChange('hi')}
          aria-pressed={currentLanguage === 'hi'}
          lang="hi"
        >
          हिन्दी
        </button>
      </div>
    </div>
  )
}
