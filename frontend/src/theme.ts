export const colors = {
  paper: '#F4F3EF',
  ink: '#121316',
  inkSecondary: '#2A2E35',
  inkMuted: '#5A606A',
  ecru: '#ECEAE4',
  white: '#FFFFFF',
  border: '#DFDCD5',
  mint: '#CDE9DC',
  mintInk: '#1B4332',
  lavender: '#E5E0F4',
  lavenderInk: '#3A2D54',
  peach: '#F9DFD5',
  peachInk: '#5C2818',
  sky: '#D9EBF5',
  skyInk: '#1B3B4B',
  charcoal: '#1B1C20',
} as const

export const cssVariables = {
  background: colors.paper,
  surface: colors.white,
  surfaceMuted: colors.ecru,
  text: colors.ink,
  textSecondary: colors.inkSecondary,
  muted: colors.inkMuted,
  border: colors.border,
  accentMint: colors.mint,
  accentLavender: colors.lavender,
  accentPeach: colors.peach,
  accentSky: colors.sky,
  accentInk: colors.charcoal,
} as const

export type Theme = 'light' | 'dark'
export const themeStorageKey = 'apk-xray-theme'

export const typography = {
  headlineXl: { fontFamily: 'Space Grotesk', fontSize: '40px', fontWeight: 600, lineHeight: '48px', letterSpacing: '-0.03em' },
  headlineXlMobile: { fontFamily: 'Space Grotesk', fontSize: '28px', fontWeight: 600, lineHeight: '36px', letterSpacing: '-0.02em' },
  headlineLg: { fontFamily: 'Space Grotesk', fontSize: '30px', fontWeight: 600, lineHeight: '38px', letterSpacing: '-0.02em' },
  headlineLgMobile: { fontFamily: 'Space Grotesk', fontSize: '22px', fontWeight: 600, lineHeight: '30px', letterSpacing: '-0.01em' },
  headlineMd: { fontFamily: 'Space Grotesk', fontSize: '20px', fontWeight: 500, lineHeight: '28px', letterSpacing: '-0.01em' },
  bodyLg: { fontFamily: 'Hanken Grotesk', fontSize: '16px', fontWeight: 400, lineHeight: '24px' },
  bodyMd: { fontFamily: 'Hanken Grotesk', fontSize: '14px', fontWeight: 400, lineHeight: '20px' },
  bodySm: { fontFamily: 'Hanken Grotesk', fontSize: '12px', fontWeight: 400, lineHeight: '16px' },
  labelLg: { fontFamily: 'JetBrains Mono', fontSize: '13px', fontWeight: 500, lineHeight: '18px', letterSpacing: '0.02em' },
  labelMd: { fontFamily: 'JetBrains Mono', fontSize: '11px', fontWeight: 500, lineHeight: '16px', letterSpacing: '0.06em' },
  labelSm: { fontFamily: 'JetBrains Mono', fontSize: '10px', fontWeight: 600, lineHeight: '14px', letterSpacing: '0.08em' },
} as const

export const spacing = {
  gutter: '1.25rem', gutterDesktop: '1.75rem', margin: '1rem', marginTablet: '2rem', marginDesktop: '3rem',
  xs: '0.25rem', sm: '0.5rem', md: '1rem', lg: '1.5rem', xl: '2.5rem',
} as const

export const radii = { sm: '0.5rem', base: '1rem', md: '1.5rem', lg: '2rem', xl: '3rem', full: '9999px' } as const
export const borders = { hairline: `1px solid ${colors.border}`, dashed: `1.5px dashed ${colors.border}` } as const
export const shadows = {
  card: '0 4px 16px -2px rgba(18, 19, 22, 0.04), 0 1px 3px 0 rgba(18, 19, 22, 0.02)',
  raised: '0 12px 36px -4px rgba(18, 19, 22, 0.06), 0 2px 8px -1px rgba(18, 19, 22, 0.03)',
  buttonHover: '0 6px 14px rgba(18, 19, 22, 0.12)',
  focus: '0 0 0 3px rgba(205, 233, 220, 0.55)',
} as const
export const breakpoints = { mobile: '767px', tablet: '768px', desktop: '1200px' } as const
