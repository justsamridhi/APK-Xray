/**
 * Shared runtime API configuration.
 * Framework detected from package.json: Vite
 */

function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_URL

  if (typeof envUrl === 'string' && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '')
  }

  // Fall back to "http://localhost:8000" only when the variable is undefined and we are in development
  if (import.meta.env.DEV) {
    return 'http://localhost:8000'
  }

  return ''
}

export const API_BASE = getApiBaseUrl()
