/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_API_UPLOAD_URL?: string
  readonly VITE_API_REPORT_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
