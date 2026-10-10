---
name: Editorial Security Inspector
colors:
  surface: '#faf9f5'
  surface-dim: '#dbdad6'
  surface-bright: '#faf9f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f4f0'
  surface-container: '#efeeea'
  surface-container-high: '#e9e8e4'
  surface-container-highest: '#e3e2df'
  on-surface: '#1b1c1a'
  on-surface-variant: '#46464b'
  inverse-surface: '#30312e'
  inverse-on-surface: '#f2f1ed'
  outline: '#76777b'
  outline-variant: '#c7c6cb'
  surface-tint: '#5e5e62'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1b1b1f'
  on-primary-container: '#848387'
  inverse-primary: '#c7c6ca'
  secondary: '#4b645a'
  on-secondary: '#ffffff'
  secondary-container: '#cde9dc'
  on-secondary-container: '#506a5f'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#1c1a28'
  on-tertiary-container: '#858293'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e3e2e6'
  primary-fixed-dim: '#c7c6ca'
  on-primary-fixed: '#1b1b1f'
  on-primary-fixed-variant: '#46464a'
  secondary-fixed: '#cde9dc'
  secondary-fixed-dim: '#b1cdc0'
  on-secondary-fixed: '#072018'
  on-secondary-fixed-variant: '#334c42'
  tertiary-fixed: '#e5e0f4'
  tertiary-fixed-dim: '#c8c4d7'
  on-tertiary-fixed: '#1c1a28'
  on-tertiary-fixed-variant: '#474555'
  background: '#faf9f5'
  on-background: '#1b1c1a'
  surface-variant: '#e3e2df'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.06em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.08em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-desktop: 1.75rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system defines a minimalist editorial security analyzer. It departs from the abrasive, neon-cyberpunk visual tropes commonly found in technical analysis software, opting instead for the clarity and poise of modern Swiss editorial publications and high-end archival research tools. 

Targeted at security researchers, Android engineers, and mobile application auditors, the experience evokes calm precision, thoroughness, and quiet technological confidence. The layout treats complex static analysis, permissions decompilation, vulnerability markers, and signature validation with tactile restraint.

The style blends **Minimalism** with **Modern Tactile Editorial**:
- Tactile warmth via textured cream and paper-like foundation surfaces.
- Pristine elevated white cards bound by crisp hairline slate borders.
- Deep midnight ink typography for uncompromising contrast and readability.
- Soft, purposeful pastel functional accents derived directly from diagnostic scanner light: pastel mint for safe/valid indicators, soft lavender for structural inspections and query routines, warm peach for critical alerts/limits, and airy sky blue for network and metadata feeds.

## Colors

The palette balances deep ink contrast against warm, paper-toned light backdrops, enlivened by diagnostic pastel washes:

- **Ink Typography & Structural Framing**: Primary midnight ink (`#121316`) anchors titles, key metrics, and decisive iconography. Secondary slate ink (`#2A2E35`) handles subheadings and active inputs, while muted neutral ink (`#5A606A`) is reserved for captions, metadata, and column headers.
- **Paper & Canvas Hierarchy**: Canvas background rests on warm paper (`#F4F3EF`), secondary nested regions use muted ecru (`#ECEAE4`), and interactive containers rely on crisp pure white (`#FFFFFF`) framed by hairline slate borders (`#DFDCD5`).
- **Functional Pastel Signatures**:
  - **Mint (`#CDE9DC`)**: Verification, safe signatures, passed rules, completed uploads.
  - **Lavender (`#E5E0F4`)**: Deep scans, AST analysis, decompilation scopes, benchmark graphs.
  - **Peach (`#F9DFD5`)**: Security limits, strict flags, permission warnings, elevated risks.
  - **Sky Blue (`#D9EBF5`)**: Manifest schemas, SDK versions, external communication traces.
- **Neutral Accent**: Pitch charcoal (`#1B1C20`) for high-priority terminal pills and dark contextual buttons (e.g., dismissing overlays or launching GitHub repository actions).

## Typography

The typographical pairing reinforces technical rigor alongside editorial restraint:

- **Headlines (Space Grotesk)**: Structural, geometric sans with subtle engineered quirks. Used for major view headers, section breakouts, and high-level analytical counters.
- **Body & Longform (Hanken Grotesk)**: Neutral, hyper-legible, modern grotesque sans. Balances dense technical descriptions, audit summaries, and diagnostic breakdowns without causing eye fatigue.
- **Labels, Metrics & Code (JetBrains Mono)**: A monospaced typeface for all hashes, file paths, package identifiers, uppercase pill tags, byte sizes, and navigation metadata.

## Layout & Spacing

The layout operates on an airy, publication-style grid system designed for data visualization and code inspection:

- **Grid Architecture**: 
  - **Desktop (1200px+)**: 12-column layout with 28px (`gutter-desktop`) gutters and generous 48px (`margin-desktop`) exterior framing. Supports dual-pane exploration (decompiled manifest on the left, rule metrics and alerts on the right).
  - **Tablet (768px – 1199px)**: 8-column layout with 20px gutters and 32px canvas margins. Sidebars collapse into docked top drawers.
  - **Mobile (< 768px)**: 4-column layout with 16px gutters and 16px margins. Metric modules stack vertically in linear card sequence.
- **Rhythm**: Component spacing prioritizes generous interior padding inside cards (`space-lg` to `space-xl`) combined with delicate internal row gaps (`space-xs` and `space-sm`) to establish clear hierarchy between technical parameters.

## Elevation & Depth

Visual hierarchy uses physical paper layering, whisper-soft drop shadows, and subtle translucent inner highlights:

- **Canvas Foundation**: Ground level (`#F4F3EF`) with flat paper absorption.
- **Cards & Analysis Modules**: Pure white (`#FFFFFF`) resting at Level 1, framed by a 1px solid hairline slate border (`#DFDCD5`). The shadow is soft, ambient, and warm: `0 4px 16px -2px rgba(18, 19, 22, 0.04), 0 1px 3px 0 rgba(18, 19, 22, 0.02)`.
- **Raised Interactive Elements (Floating Panels & Modals)**: Level 2 elevation featuring a dual-boundary definition: `0 12px 36px -4px rgba(18, 19, 22, 0.06), 0 2px 8px -1px rgba(18, 19, 22, 0.03)`.
- **Embossed Pastel Tints**: Buttons and metric pills feature a 1px inner ambient rim (`inset 0 1px 0 rgba(255, 255, 255, 0.7)`) to mimic debossed physical badges.

## Shapes

The design uses a pill-forward geometric system that balances technical precision with tactile softness:

- **Pill Primitives (`roundedness: 3`)**: Navigation tags, filter chips, category pills, status indicators, and action buttons use smooth full-radius capsules (radii ranging from 1rem to 3rem).
- **Surface Containers**: Cards and inspector modules retain gentle, rounded-corner architecture (`rounded-xl` at 1.5rem / 24px) to soften dense data tables.
- **Micro-Elements**: Checkboxes, toggle switches, and code snippets use smaller 8px to 12px radii to ensure structural integrity in dense layouts.

## Components

### Buttons
- **Primary Action (Dark Ink)**: Deep charcoal (`#121316`) background, pure white text, pill shape (`rounded-full`), padded `0.75rem 1.5rem`. Subtle hover translates 1px upwards with shadow `0 6px 14px rgba(18, 19, 22, 0.12)`.
- **Secondary Action (Pastel Diagnostic)**: Mint (`#CDE9DC`), lavender (`#E5E0F4`), or peach (`#F9DFD5`) background with primary ink text (`#121316`). Pill silhouette, 1px inner white highlight.
- **Tertiary Action (Hairline Paper)**: Background transparent or `#FFFFFF`, 1px border `#DFDCD5`, ink text `#2A2E35`. On hover, fills with `#ECEAE4`.

### Chips & Status Badges
- Compact capsules styled with monospaced text (`label-md`). 
- **Safe / Valid**: Mint (`#CDE9DC`) badge with `#1B4332` ink.
- **Scan / Analysis**: Lavender (`#E5E0F4`) badge with `#3A2D54` ink.
- **Warning / Risk**: Peach (`#F9DFD5`) badge with `#5C2818` ink.
- **Schema / Network**: Sky Blue (`#D9EBF5`) badge with `#1B3B4B` ink.

### Cards & Analytical Panels
- White `#FFFFFF` foundation, 1px `#DFDCD5` border, `rounded-xl` (24px corner radius), 24px internal padding.
- Card header zones utilize faint `#ECEAE4` hairline bottom dividers (1px solid).
- Data tiles nested within cards drop back down to `#F4F3EF` to create layered depth without heavy borders.

### Input Fields & Search Bars
- Background `#FFFFFF` or `#ECEAE4` inset, pill-shaped contour with 1px border `#DFDCD5`.
- Text typed in `Hanken Grotesk` 14px (`body-md`), with placeholder text in `#5A606A`.
- Focus state applies a 1px border in `#121316` and a soft mint ring glow: `0 0 0 3px rgba(205, 233, 220, 0.55)`.

### Selection Controls (Checkboxes & Radios)
- Rounded geometric squares (checkbox, 6px radius) and concentric rings (radio).
- Default: 1px border `#DFDCD5`, surface `#FFFFFF`.
- Checked: Background filled with midnight ink `#121316` featuring a pastel mint (`#CDE9DC`) checkmark or central indicator dot.

### Lists & Key-Value Inspection Rows
- Alternating or hairline-separated data rows (`#DFDCD5` bottom border, 1px).
- Left column: Property / permission key in `JetBrains Mono` (`label-md`, `#5A606A`).
- Right column: Resolved value or flag in `Hanken Grotesk` (`body-md`, `#121316`), paired with appropriate pastel status badge.

### File Drag-and-Drop Target
- Dashed 1.5px hairline border (`#DFDCD5`), filled with layered paper gradient (`#F4F3EF` to `#ECEAE4`), pill or 28px rounded rectangle.
- Features centered diagnostic scan icon with subtle pulsing mint glow.