import React, { useEffect, useRef, useState, useCallback, type ReactNode } from 'react'

/**
 * Error boundary wrapper for animated components
 * Displays fallback content on error without crashing the app
 */
class AnimationErrorBoundary extends React.Component<
  { children: ReactNode; fallback?: ReactNode },
  { hasError: boolean }
> {
  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    console.error('Animation error:', error)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <>{this.props.children}</>
    }
    return this.props.children
  }
}

export interface AnimatedCounterProps {
  value: number
  duration?: number // Animation duration in ms (default: 1000)
  prefix?: string   // Text before number (e.g., "$")
  suffix?: string   // Text after number (e.g., "%")
  locale?: string   // Locale for number formatting (default: "en")
  onComplete?: () => void // Callback when animation completes
}

/**
 * Formats a number according to the specified locale
 */
function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(locale).format(Math.round(value))
}

/**
 * Eases out the animation progress for a natural feel
 */
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

/**
 * AnimatedCounter - Animates numeric values counting up from zero to target value
 * Uses requestAnimationFrame for smooth 60fps counting animation
 * Respects prefers-reduced-motion accessibility preference
 */
export function AnimatedCounter({
  value,
  duration = 1000,
  prefix = '',
  suffix = '',
  locale = 'en',
  onComplete
}: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState(0)
  const animationRef = useRef<number | null>(null)
  const startTimeRef = useRef<number | null>(null)
  const previousValueRef = useRef(0)
  const previousDurationRef = useRef(duration)

  const animate = useCallback((startTime: number) => {
    const elapsed = performance.now() - startTime
    const progress = Math.min(elapsed / previousDurationRef.current, 1)
    const easedProgress = easeOutCubic(progress)
    const currentValue = previousValueRef.current + (value - previousValueRef.current) * easedProgress
    
    setDisplayValue(currentValue)
    
    if (progress < 1) {
      animationRef.current = requestAnimationFrame(() => animate(startTime))
    } else {
      setDisplayValue(value)
      // animation complete
      onComplete?.()
    }
  }, [value, onComplete])

  useEffect(() => {
    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    
    if (prefersReducedMotion) {
      // Skip animation, show final value directly
      setDisplayValue(value)
      return
    }

    // Start animation
    // animation started
    previousValueRef.current = displayValue
    previousDurationRef.current = duration
    
    // Cancel any existing animation
    if (animationRef.current !== null) {
      cancelAnimationFrame(animationRef.current)
    }
    
    // Start new animation
    startTimeRef.current = performance.now()
    animationRef.current = requestAnimationFrame(() => animate(startTimeRef.current!))

    // Cleanup on unmount
    return () => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [value, duration, animate, displayValue])

  return (
    <AnimationErrorBoundary fallback={<span>{prefix}{formatNumber(value, locale)}{suffix}</span>}>
      <span className="counter-animate" aria-live="polite" aria-atomic="true">
        {prefix}{formatNumber(displayValue, locale)}{suffix}
      </span>
    </AnimationErrorBoundary>
  )
}

export default AnimatedCounter

