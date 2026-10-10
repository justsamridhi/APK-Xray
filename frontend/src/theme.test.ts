import { describe, expect, it } from 'vitest'
import { borders, breakpoints, colors, radii, shadows, spacing, typography } from './theme'

describe('light design tokens', () => {
  it('exports the palette from DESIGN.md', () => {
    expect(colors.paper).toBe('#F4F3EF')
    expect(colors.ink).toBe('#121316')
    expect(colors.border).toBe('#DFDCD5')
    expect(colors.mint).toBe('#CDE9DC')
    expect(colors.lavender).toBe('#E5E0F4')
    expect(colors.peach).toBe('#F9DFD5')
    expect(colors.sky).toBe('#D9EBF5')
  })
  it('exports the documented type and layout scales', () => {
    expect(typography.headlineXl.fontFamily).toBe('Space Grotesk')
    expect(typography.bodyMd.fontFamily).toBe('Hanken Grotesk')
    expect(typography.labelMd.fontFamily).toBe('JetBrains Mono')
    expect(spacing.xl).toBe('2.5rem')
    expect(radii.md).toBe('1.5rem')
    expect(borders.hairline).toContain(colors.border)
    expect(shadows.card).toContain('rgba(18, 19, 22, 0.04)')
    expect(breakpoints.tablet).toBe('768px')
  })
})
