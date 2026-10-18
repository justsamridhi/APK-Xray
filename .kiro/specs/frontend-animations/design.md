# Frontend Animations Design Document

## Overview

This design document specifies the frontend animation implementation for APK-Xray, enhancing user experience with smooth, purposeful animations while maintaining accessibility and performance. The animations are purely decorative and do not affect functionality.

### 1.1 Animation Principles

The following principles guide all animation implementations:

- **Purposeful Motion**: Every animation serves a functional purpose (feedback, guidance, or state indication)
- **Performance First**: Animations use CSS transforms and opacity for 60fps performance
- **Accessibility**: Respects `prefers-reduced-motion` and provides non-visual feedback
- **Progressive Enhancement**: Falls back gracefully when animations are unavailable
- **Theme Compatible**: Works seamlessly in both light and dark themes

### 1.2 Animation Scope

The following sections will receive animations:

1. **Landing Page Hero Section**: Badge and text reveal animations
2. **Dashboard**: Score counter animation and gauge reveal
3. **Upload Flow**: Progress indicator and file validation feedback
4. **Findings Display**: Staggered reveal of finding cards
5. **Loading States**: Skeleton screens with shimmer effects

---

## Architecture

### 2.1 High-Level Architecture

The animation system follows a layered architecture:

```
┌─────────────────────────────────────────────────────┐
│           App.tsx (Integration Layer)               │
│     - Animation class application                   │
│     - Component orchestration                       │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│      Animated Components (React Components)         │
│  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  ScoreGauge     │  │      StaggeredList      │  │
│  │  (SVG Gauge)    │  │   (List Animations)     │  │
│  └─────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ AnimatedCounter │  │    LoadingSkeleton      │  │
│  │ (Number Count)  │  │   (Shimmer States)      │  │
│  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│     CSS Animation System (styles.css)               │
│  - Keyframes (fadeInUp, scanPulse, shimmer...)     │
│  - Utility classes (.animate-delay-100, ...)       │
│  - Theme variables integration                     │
└─────────────────────────────────────────────────────┘
```

### 2.2 Animation Flow

1. **Initialization**: App renders with animation classes applied
2. **CSS Animation**: Browser handles CSS-based animations (fade, slide, scale)
3. **JS Animation**: React components manage complex animations (counter, gauge)
4. **Cleanup**: Components unmount and clean up animation resources

### 2.3 Performance Architecture

- **CSS Layer**: Hardware-accelerated transforms and opacity changes
- **JS Layer**: requestAnimationFrame for frame-perfect JavaScript animations
- **Optimization**: will-change hints for complex animations
- **Memory Management**: Explicit cleanup of animation resources

---

## Components and Interfaces

### 3.1 CSS Animation System

#### 3.1.1 Keyframes

Add the following keyframes to `frontend/src/styles.css`:

```css
/* Fade in upward movement */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Scanning pulse effect */
@keyframes scanPulse {
  0% {
    opacity: 0;
    transform: scale(0.95);
  }
  50% {
    opacity: 0.8;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(1.05);
  }
}

/* Shimmer loading effect */
@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

/* Number counter counting up */
@keyframes countUp {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Slide in from side */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* Fade in */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Scale in */
@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Pulse for attention */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Rotate animation for loading */
@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
```

#### 3.1.2 Animation Utility Classes

Add utility classes for consistent animation application:

```css
/* Base animation class */
.animate {
  animation-fill-mode: both;
  animation-timing-function: ease-out;
}

/* Duration utilities */
.animate-duration-300 { animation-duration: 300ms; }
.animate-duration-500 { animation-duration: 500ms; }
.animate-duration-700 { animation-duration: 700ms; }
.animate-duration-1000 { animation-duration: 1000ms; }

/* Delay utilities for staggered animations */
.animate-delay-100 { animation-delay: 100ms; }
.animate-delay-150 { animation-delay: 150ms; }
.animate-delay-200 { animation-delay: 200ms; }
.animate-delay-300 { animation-delay: 300ms; }
.animate-delay-400 { animation-delay: 400ms; }
.animate-delay-500 { animation-delay: 500ms; }

/* Animation type utilities */
.animate-fade-in { animation-name: fadeIn; }
.animate-fade-in-up { animation-name: fadeInUp; }
.animate-scale-in { animation-name: scaleIn; }
.animate-slide-in { animation-name: slideIn; }
.animate-pulse { animation-name: pulse; animation-iteration-count: infinite; }

/* Timing function overrides */
.animate-ease-in { animation-timing-function: ease-in; }
.animate-ease-in-out { animation-timing-function: ease-in-out; }
.animate-linear { animation-timing-function: linear; }

/* Staggered list container */
.animate-stagger-children > * {
  opacity: 0;
}

.animate-stagger-children > *.animate {
  opacity: 1;
}

/* Loading skeleton base */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--surface-muted) 25%,
    var(--surface) 50%,
    var(--surface-muted) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

/* Shimmer variants */
.skeleton-text {
  height: 1em;
  border-radius: 4px;
}

.skeleton-title {
  height: 1.5em;
  width: 60%;
  border-radius: 6px;
}

.skeleton-card {
  height: 120px;
  border-radius: 12px;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

/* Gauge animation */
.gauge-fill {
  transition: stroke-dashoffset 1s ease-out;
}

/* Counter animation */
.counter-animate {
  display: inline-block;
}
```

### 3.2 AnimatedCounter Component

**Purpose**: Animates numeric values counting up from zero to target value

**Location**: `frontend/src/components/AnimatedCounter.tsx`

**Props Interface**:
```typescript
interface AnimatedCounterProps {
  value: number;
  duration?: number; // Animation duration in ms (default: 1000)
  prefix?: string;   // Text before number (e.g., "$")
  suffix?: string;   // Text after number (e.g., "%")
  locale?: string;   // Locale for number formatting (default: "en")
  onComplete?: () => void; // Callback when animation completes
}
```

**Implementation Requirements**:
- Uses `requestAnimationFrame` for smooth counting
- Supports number formatting with locale
- Handles rapid prop changes gracefully
- Cleans up animation frame on unmount
- Respects `prefers-reduced-motion` preference
- Includes error boundary wrapper

**Error Handling**:
- Wrap with ErrorBoundary component
- Fallback to displaying static value on error

### 3.3 StaggeredList Component

**Purpose**: Renders a list with staggered child reveal animations

**Location**: `frontend/src/components/StaggeredList.tsx`

**Props Interface**:
```typescript
interface StaggeredListProps {
  items: Array<{ id: string | number; [key: string]: unknown }>;
  children: (item: T, index: number) => React.ReactNode;
  staggerDelay?: number;      // Delay between each item (default: 100)
  animationType?: 'fadeUp' | 'slideIn' | 'scaleIn';
  containerClassName?: string;
  itemClassName?: string;
}
```

**Implementation Requirements**:
- Uses CSS animation with staggered delays
- Maintains original DOM order for accessibility
- Supports dynamic item counts
- Handles empty state gracefully
- Respects `prefers-reduced-motion`

**Error Handling**:
- Wrap each item in ErrorBoundary
- Show error state for failed items without breaking list

### 3.4 LoadingSkeleton Component

**Purpose**: Displays skeleton loading states with shimmer effect

**Location**: `frontend/src/components/LoadingSkeleton.tsx`

**Props Interface**:
```typescript
interface LoadingSkeletonProps {
  variant?: 'text' | 'title' | 'card' | 'avatar' | 'custom';
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  count?: number; // Number of skeleton elements to render
}
```

**Implementation Requirements**:
- Uses CSS shimmer animation
- Adapts to light/dark themes via CSS variables
- Supports custom dimensions
- Renders multiple skeletons for lists
- Pauses animation when off-screen (optional, for performance)

**Error Handling**:
- Minimal error surface (CSS-based rendering)
- Fallback to static placeholder if CSS fails

### 3.5 ScoreGauge Component

**Purpose**: SVG radial gauge with animated fill and counter

**Location**: `frontend/src/components/ScoreGauge.tsx`

**Props Interface**:
```typescript
interface ScoreGaugeProps {
  score: number;           // Score value 0-100
  maxScore?: number;       // Maximum possible score (default: 100)
  size?: number;           // Gauge diameter in pixels (default: 200)
  strokeWidth?: number;    // Stroke width in pixels (default: 12)
  severity: 'safe' | 'scan' | 'warning'; // Color theme
  animated?: boolean;      // Enable animation (default: true)
  showCounter?: boolean;   // Show counter in center (default: true)
  label?: string;          // Label text below gauge
}
```

**Implementation Requirements**:
- SVG-based for crisp rendering at any size
- Smooth stroke-dasharray animation
- Color-coded based on severity level
- Accessible with proper ARIA labels
- Responsive to theme changes

**Color Mapping**:
- safe (low risk): `--mint-ink` / `--mint-soft`
- scan (medium risk): `--sky-ink` / `--sky-soft`
- warning/high risk: `--peach-ink` / `--peach-soft`

**Error Handling**:
- Validate score is within bounds
- Fallback to static gauge if animation fails
- Error boundary wrapper for React errors

---

## Data Models

### 4.1 Animation Configuration Data

```typescript
interface AnimationConfig {
  duration: number;
  delay: number;
  easing: string;
  stagger: number;
}

const defaultAnimationConfig: AnimationConfig = {
  duration: 1000,
  delay: 0,
  easing: 'ease-out',
  stagger: 100
};
```

### 4.2 Theme-Aware Color Data

```typescript
interface ThemeColors {
  safe: {
    stroke: string;
    background: string;
  };
  scan: {
    stroke: string;
    background: string;
  };
  warning: {
    stroke: string;
    background: string;
  };
}

const themeColors: ThemeColors = {
  safe: {
    stroke: 'var(--mint-ink)',
    background: 'var(--mint-soft)'
  },
  scan: {
    stroke: 'var(--sky-ink)',
    background: 'var(--sky-soft)'
  },
  warning: {
    stroke: 'var(--peach-ink)',
    background: 'var(--peach-soft)'
  }
};
```

### 4.3 Gauge Geometry Data

```typescript
interface GaugeGeometry {
  radius: number;
  circumference: number;
  strokeWidth: number;
  center: { x: number; y: number };
}

function calculateGaugeGeometry(size: number, strokeWidth: number): GaugeGeometry {
  const radius = (size - strokeWidth) / 2;
  return {
    radius,
    circumference: 2 * Math.PI * radius,
    strokeWidth,
    center: { x: size / 2, y: size / 2 }
  };
}
```

### 4.4 Counter Animation State

```typescript
interface CounterState {
  currentValue: number;
  targetValue: number;
  startTime: number;
  duration: number;
  isAnimating: boolean;
}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Animation Completion Guarantees

*For any* animated component, the animation SHALL complete within the specified duration without visual artifacts or stuck states

**Validates: Requirements 4.4**

### Property 2: Theme Compatibility

*For any* animation applied to any element, the visual appearance SHALL be consistent between light and dark themes using CSS variables

**Validates: Requirements 5.3**

### Property 3: Accessibility Respect

*For any* user with `prefers-reduced-motion: reduce`, no animations SHALL play, and the UI SHALL display in static mode

**Validates: Requirements 4.5**

### Property 4: Functional Preservation

*For any* animation applied to UI components, all interactive functionality (clicks, keyboard navigation, focus management) SHALL remain fully operational

**Validates: Requirements 4.2**

### Property 5: Performance Boundary

*For any* animation sequence, the frame rate SHALL remain at or above 55fps during execution on typical hardware

**Validates: Requirements 4.4**

### Property 6: Error Resilience

*For any* animated component that encounters an error, the UI SHALL display fallback content and maintain system stability without crashing

**Validates: Requirements 4.3**

---

## Error Handling

### 5.1 Error Boundary Implementation

Each animated component includes an error boundary wrapper:

```tsx
class AnimationErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean }
> {
  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error('Animation error:', error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <>{this.props.children}</>;
    }
    return this.props.children;
  }
}
```

### 5.2 Fallback Strategies

**AnimatedCounter Fallback**: Display static value
**StaggeredList Fallback**: Render items without animation
**LoadingSkeleton Fallback**: Static placeholder div
**ScoreGauge Fallback**: Static SVG gauge

### 5.3 Error Recovery

- Graceful degradation to static UI
- Console logging for debugging
- No component crashes
- Automatic retry on next render

---

## Testing Strategy

### 6.1 Unit Testing

- **AnimatedCounter**: Test counting animation with various durations and values
- **StaggeredList**: Test staggered delays and animation class application
- **LoadingSkeleton**: Test shimmer animation and theme compatibility
- **ScoreGauge**: Test gauge geometry and animation timing

### 6.2 Integration Testing

- **Animation Sequences**: Verify animations play in correct order
- **Theme Switching**: Test animations adapt to theme changes
- **Component Interaction**: Verify animations don't break interactivity
- **Responsive Behavior**: Test animations on different screen sizes

### 6.3 Visual Testing

- **Screenshot Comparisons**: Baseline screenshots for each animated state
- **Theme Verification**: Light/dark mode visual consistency
- **Cross-browser Testing**: Chrome, Firefox, Safari, Edge
- **Animation Timing**: Verify durations match specifications

### 6.4 Performance Testing

- **Frame Rate**: Target 60fps with 16ms frame budget
- **Memory Usage**: No memory leaks during animations
- **CPU Usage**: Efficient animation performance
- **Battery Impact**: Minimal drain on mobile devices

### 6.5 Accessibility Testing

- **Screen Readers**: Verify animations don't interfere with screen reader announcements
- **Keyboard Navigation**: Ensure keyboard users can navigate during animations
- **Reduced Motion**: Test `prefers-reduced-motion` detection
- **Focus Management**: Verify focus isn't lost during animations

---

## Implementation Details

### 7.1 CSS Animation Keyframes

Add the following keyframes to `frontend/src/styles.css`:

```css
/* Fade in upward movement */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Scanning pulse effect */
@keyframes scanPulse {
  0% {
    opacity: 0;
    transform: scale(0.95);
  }
  50% {
    opacity: 0.8;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(1.05);
  }
}

/* Shimmer loading effect */
@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

/* Number counter counting up */
@keyframes countUp {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Slide in from side */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* Fade in */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Scale in */
@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Pulse for attention */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Rotate animation for loading */
@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
```

### 7.2 Animation Utility Classes

Add utility classes for consistent animation application:

```css
/* Base animation class */
.animate {
  animation-fill-mode: both;
  animation-timing-function: ease-out;
}

/* Duration utilities */
.animate-duration-300 { animation-duration: 300ms; }
.animate-duration-500 { animation-duration: 500ms; }
.animate-duration-700 { animation-duration: 700ms; }
.animate-duration-1000 { animation-duration: 1000ms; }

/* Delay utilities for staggered animations */
.animate-delay-100 { animation-delay: 100ms; }
.animate-delay-150 { animation-delay: 150ms; }
.animate-delay-200 { animation-delay: 200ms; }
.animate-delay-300 { animation-delay: 300ms; }
.animate-delay-400 { animation-delay: 400ms; }
.animate-delay-500 { animation-delay: 500ms; }

/* Animation type utilities */
.animate-fade-in { animation-name: fadeIn; }
.animate-fade-in-up { animation-name: fadeInUp; }
.animate-scale-in { animation-name: scaleIn; }
.animate-slide-in { animation-name: slideIn; }
.animate-pulse { animation-name: pulse; animation-iteration-count: infinite; }

/* Timing function overrides */
.animate-ease-in { animation-timing-function: ease-in; }
.animate-ease-in-out { animation-timing-function: ease-in-out; }
.animate-linear { animation-timing-function: linear; }

/* Staggered list container */
.animate-stagger-children > * {
  opacity: 0;
}

.animate-stagger-children > *.animate {
  opacity: 1;
}

/* Loading skeleton base */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--surface-muted) 25%,
    var(--surface) 50%,
    var(--surface-muted) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

/* Shimmer variants */
.skeleton-text {
  height: 1em;
  border-radius: 4px;
}

.skeleton-title {
  height: 1.5em;
  width: 60%;
  border-radius: 6px;
}

.skeleton-card {
  height: 120px;
  border-radius: 12px;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

/* Gauge animation */
.gauge-fill {
  transition: stroke-dashoffset 1s ease-out;
}

/* Counter animation */
.counter-animate {
  display: inline-block;
}
```

### 7.3 Component Specifications

#### 7.3.1 AnimatedCounter.tsx

**Purpose**: Animates numeric values counting up from zero to target value

**Location**: `frontend/src/components/AnimatedCounter.tsx`

**Props Interface**:
```typescript
interface AnimatedCounterProps {
  value: number;
  duration?: number; // Animation duration in ms (default: 1000)
  prefix?: string;   // Text before number (e.g., "$")
  suffix?: string;   // Text after number (e.g., "%")
  locale?: string;   // Locale for number formatting (default: "en")
  onComplete?: () => void; // Callback when animation completes
}
```

**Implementation Requirements**:
- Uses `requestAnimationFrame` for smooth counting
- Supports number formatting with locale
- Handles rapid prop changes gracefully
- Cleans up animation frame on unmount
- Respects `prefers-reduced-motion` preference
- Includes error boundary wrapper

**Pseudocode**:
```
1. On mount or value change:
   a. Check prefers-reduced-motion preference
   b. If reduced motion: set value directly
   c. Otherwise: start counting animation
2. Animation loop:
   a. Use requestAnimationFrame
   b. Interpolate from previous to target value
   c. Apply easing function for natural feel
   d. Update displayed value each frame
   e. Stop when elapsed time >= duration
3. Cleanup:
   a. Cancel pending animation frame on unmount
   b. Clear any timers
```

**Error Handling**:
- Wrap with ErrorBoundary component
- Fallback to displaying static value on error

#### 7.3.2 StaggeredList.tsx

**Purpose**: Renders a list with staggered child reveal animations

**Location**: `frontend/src/components/StaggeredList.tsx`

**Props Interface**:
```typescript
interface StaggeredListProps {
  items: Array<{ id: string | number; [key: string]: unknown }>;
  children: (item: T, index: number) => React.ReactNode;
  staggerDelay?: number;      // Delay between each item (default: 100)
  animationType?: 'fadeUp' | 'slideIn' | 'scaleIn';
  containerClassName?: string;
  itemClassName?: string;
}
```

**Implementation Requirements**:
- Uses CSS animation with staggered delays
- Maintains original DOM order for accessibility
- Supports dynamic item counts
- Handles empty state gracefully
- Respects `prefers-reduced-motion`

**Pseudocode**:
```
1. Render container with animate-stagger-children class
2. For each item:
   a. Calculate delay: index * staggerDelay
   b. Apply animation class with delay
   c. Render child component with item data
3. On animation end:
   a. Remove animation classes
   b. Items become fully visible
```

**Error Handling**:
- Wrap each item in ErrorBoundary
- Show error state for failed items without breaking list

#### 7.3.3 LoadingSkeleton.tsx

**Purpose**: Displays skeleton loading states with shimmer effect

**Location**: `frontend/src/components/LoadingSkeleton.tsx`

**Props Interface**:
```typescript
interface LoadingSkeletonProps {
  variant?: 'text' | 'title' | 'card' | 'avatar' | 'custom';
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  count?: number; // Number of skeleton elements to render
}
```

**Implementation Requirements**:
- Uses CSS shimmer animation
- Adapts to light/dark themes via CSS variables
- Supports custom dimensions
- Renders multiple skeletons for lists
- Pauses animation when off-screen (optional, for performance)

**Pseudocode**:
```
1. Determine skeleton variant dimensions
2. Apply skeleton CSS class with shimmer animation
3. Render with proper border-radius for theme
4. For multiple skeletons: render count number
```

**Error Handling**:
- Minimal error surface (CSS-based rendering)
- Fallback to static placeholder if CSS fails

#### 7.3.4 ScoreGauge.tsx

**Purpose**: SVG radial gauge with animated fill and counter

**Location**: `frontend/src/components/ScoreGauge.tsx`

**Props Interface**:
```typescript
interface ScoreGaugeProps {
  score: number;           // Score value 0-100
  maxScore?: number;       // Maximum possible score (default: 100)
  size?: number;           // Gauge diameter in pixels (default: 200)
  strokeWidth?: number;    // Stroke width in pixels (default: 12)
  severity: 'safe' | 'scan' | 'warning'; // Color theme
  animated?: boolean;      // Enable animation (default: true)
  showCounter?: boolean;   // Show counter in center (default: true)
  label?: string;          // Label text below gauge
}
```

**Implementation Requirements**:
- SVG-based for crisp rendering at any size
- Smooth stroke-dasharray animation
- Color-coded based on severity level
- Accessible with proper ARIA labels
- Responsive to theme changes

**Color Mapping**:
- safe (low risk): `--mint-ink` / `--mint-soft`
- scan (medium risk): `--sky-ink` / `--sky-soft`
- warning/high risk: `--peach-ink` / `--peach-soft`

**Pseudocode**:
```
1. Calculate circle geometry:
   a. Circumference = 2 * PI * radius
   b. Offset = circumference * (1 - score/max)
2. Render SVG with two circles:
   a. Background circle (muted color)
   b. Foreground circle (severity color, animated stroke-dashoffset)
3. Center content:
   a. Animated counter (if enabled)
   b. Label text (if provided)
4. Animate:
   a. CSS transition on stroke-dashoffset
   b. Or requestAnimationFrame for counter
```

**Error Handling**:
- Validate score is within bounds
- Fallback to static gauge if animation fails
- Error boundary wrapper for React errors

---

## Integration Points

### 8.1 App.tsx Integration

The following sections in `App.tsx` will receive animation classes:

#### Landing Page (AnalyzePage Component)
```tsx
// Hero panel animations
<section className="hero-panel animate-fade-in-up animate-duration-700">
  <div className="animate-fade-in-up animate-delay-100">
    <Badge ... />
  </div>
  <h1 className="animate-fade-in-up animate-delay-200">Evidence-first Android static analysis.</h1>
  <p className="animate-fade-in-up animate-delay-300">...</p>
</section>

// Upload section
<Card className="upload-placeholder animate-fade-in-up animate-delay-400">
  <h2 className="animate-fade-in">Analyzing an APK</h2>
</Card>

// Pipeline steps
<div className="pipeline-grid animate-stagger-children">
  {steps.map((step, index) => (
    <div 
      key={step.label}
      className="pipeline-step animate-fade-in-up"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      ...
    </div>
  ))}
</div>
```

#### Report Page (ReportContent Component)
```tsx
// Report summary with gauge
<div className="report-summary animate-fade-in-up">
  <div className="report-score">
    <ScoreGauge 
      score={report.score.value} 
      severity={scoreTone}
      animated={true}
    />
  </div>
</div>

// Findings with stagger effect
<div className="finding-grid animate-stagger-children">
  {report.findings.map((finding, index) => (
    <Card 
      key={finding.ruleId}
      className="finding-card animate-fade-in-up"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      ...
    </Card>
  ))}
</div>

// Breakdown table
<Card className="breakdown-card animate-fade-in animate-delay-200">
  ...
</Card>
```

### 8.2 Theme Integration

All animations use CSS custom properties to ensure theme compatibility:

```css
/* Example: Shimmer adapts to theme */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--surface-muted) 25%,
    var(--surface) 50%,
    var(--surface-muted) 75%
  );
}

/* Gauge colors use theme variables */
.gauge-safe {
  stroke: var(--mint-ink);
  background: var(--mint-soft);
}

.gauge-warning {
  stroke: var(--peach-ink);
  background: var(--peach-soft);
}

.gauge-scan {
  stroke: var(--sky-ink);
  background: var(--sky-soft);
}
```

### 8.3 Font Family Consistency

All animated text maintains consistent font usage:

- Headers: `font-family: 'Space Grotesk', sans-serif;`
- Body/UI: `font-family: 'Hanken Grotesk', sans-serif;`
- Code/Monospace: `font-family: 'JetBrains Mono', monospace;`

---

## Files to Modify

### 9.1 New Files

| File | Purpose |
|------|---------|
| `frontend/src/components/AnimatedCounter.tsx` | Numeric counter animation component |
| `frontend/src/components/StaggeredList.tsx` | Staggered list reveal component |
| `frontend/src/components/LoadingSkeleton.tsx` | Skeleton loading state component |
| `frontend/src/components/ScoreGauge.tsx` | SVG radial gauge component |

### 9.2 Modified Files

| File | Changes |
|------|---------|
| `frontend/src/styles.css` | Add keyframes, utility classes, shimmer styles |
| `frontend/src/App.tsx` | Add animation classes to components |

### 9.3 Unchanged Files (Safety Requirement)

- All backend files remain unchanged
- API integration unchanged
- Report schema unchanged
- Theme configuration unchanged

---

## Safety Requirements

### 10.1 Zero Backend Changes

**Confirmed**: No backend modifications required. All animations are frontend-only enhancements.

### 10.2 Preserve Existing Functionality

- **Graceful Degradation**: If animations fail or are disabled, the UI displays correctly without animations
- **Core Functionality**: Upload, analysis, and report display work identically
- **No Breaking Changes**: Animation classes add visual effects only, no structural changes

### 10.3 Error Boundaries

Each animated component includes an error boundary wrapper:

```tsx
class AnimationErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean }
> {
  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error('Animation error:', error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <>{this.props.children}</>;
    }
    return this.props.children;
  }
}
```

### 10.4 Performance Optimization

**Animation Performance Guidelines**:

1. **Use CSS Transforms**: All animations use `transform` and `opacity` only
2. **RequestAnimationFrame**: For JavaScript-driven animations (counter)
3. **Cleanup**: All animation frames and timers cleaned up on unmount
4. **will-change**: Apply sparingly for complex animations
5. **Off-screen Optimization**: Pause animations when components are not visible (optional, for performance)

**Performance Budgets**:
- Animation frame budget: 16ms (60fps)
- Total animation time per section: < 1000ms
- Maximum concurrent animations: 5 per section

### 10.5 Accessibility

**prefers-reduced-motion Support**:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  
  .animate-stagger-children > * {
    opacity: 1;
    transform: none;
  }
}
```

**Non-Visual Feedback**:
- All animated state changes have ARIA live regions
- Progress indicators use `role="progressbar"`
- Loading states use `aria-busy` and `aria-label`
- Focus management maintained throughout animations

---

## Acceptance Criteria

### Animation Quality
- [ ] Animations are smooth and purposeful
- [ ] No jank, lag, or dropped frames
- [ ] Consistent timing and easing across elements
- [ ] Theme-aware coloring

### Integration
- [ ] Landing page has hero section animations
- [ ] Report page has score gauge animation
- [ ] Findings reveal with stagger effect
- [ ] Upload progress has visual feedback

### Safety
- [ ] Zero backend changes
- [ ] Error boundaries on all animated components
- [ ] Reduced motion preference respected
- [ ] Existing functionality preserved

### Performance
- [ ] 60fps animations
- [ ] No memory leaks
- [ ] Proper cleanup on unmount
- [ ] Efficient CSS properties used

### Accessibility
- [ ] Screen reader compatible
- [ ] Keyboard navigation maintained
- [ ] Non-visual feedback provided
- [ ] prefers-reduced-motion supported

---

## Timeline Estimate

- **Design Document**: 1 hour
- **CSS Implementation**: 2 hours
- **Component Development**: 6 hours
- **Integration**: 2 hours
- **Testing & Polish**: 3 hours
- **Total**: ~14 hours

---

## References

- [MDN: CSS Animations](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Animations)
- [MDN: CSS Transitions](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Transitions)
- [Web Accessibility: Animation](https://www.w3.org/WAI/WCAG21/Understanding/animation-from-interactions.html)
- [React: Performance Optimization](https://react.dev/learn/render-and-commit)
- [CSS-Tricks: Animation Performance](https://css-tricks.com/almanac/properties/a/animation/)