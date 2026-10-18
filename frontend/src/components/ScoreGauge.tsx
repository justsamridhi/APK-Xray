import React, { useEffect, useState, useMemo, type CSSProperties } from 'react'
import { AnimatedCounter } from './AnimatedCounter'

export type Severity = 'safe' | 'scan' | 'warning'

export interface ScoreGaugeProps {
  score: number           // Score value 0-100
  maxScore?: number       // Maximum possible score (default: 100)
  size?: number           // Gauge diameter in pixels (default: 200)
  strokeWidth?: number    // Stroke width in pixels (default: 12)
  severity: Severity      // Color theme
  animated?: boolean      // Enable animation (default: true)
  showCounter?: boolean   // Show counter in center (default: true)
  label?: string          // Label text below gauge
}

/**
 * Theme colors for gauge based on severity level
 */
const severityColors: Record<Severity, { stroke: string; background: string }> = {
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
}

/**
 * Error boundary wrapper for gauge component
 */
class GaugeErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean }
> {
  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    console.error('ScoreGauge error:', error)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <div className="score-gauge-fallback">Score unavailable</div>
    }
    return this.props.children
  }
}

/**
 * Calculates gauge circle geometry
 */
function calculateGeometry(size: number, strokeWidth: number): {
  radius: number
  circumference: number
  center: { x: number; y: number }
  dashArray: number
  dashOffset: number
} {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const center = { x: size / 2, y: size / 2 }
  
  // Calculate stroke-dasharray and offset for the score
  const scoreRatio = 0.75 // Gauge covers 270 degrees (3/4 of circle)
  const dashArray = circumference * scoreRatio
  const dashOffset = dashArray * (1 - 1) // Full circle initially
  
  return {
    radius,
    circumference,
    center,
    dashArray,
    dashOffset
  }
}

/**
 * ScoreGauge - SVG radial gauge with animated fill and counter
 * Uses SVG for crisp rendering at any size
 * Color-coded based on severity level
 * Accessible with proper ARIA labels
 */
export function ScoreGauge({
  score,
  maxScore = 100,
  size = 200,
  strokeWidth = 12,
  severity = 'safe',
  animated = true,
  showCounter = true,
  label
}: ScoreGaugeProps) {
  const [displayScore, setDisplayScore] = useState(0)
  const [strokeDashOffset, setStrokeDashOffset] = useState(0)
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  // Validate and clamp score
  const clampedScore = Math.max(0, Math.min(score, maxScore))
  const scorePercentage = clampedScore / maxScore

  // Calculate gauge geometry
  const geometry = useMemo(() => calculateGeometry(size, strokeWidth), [size, strokeWidth])
  const colors = severityColors[severity]
  
  // Calculate stroke-dashoffset for current score
  const targetOffset = geometry.dashArray * (1 - scorePercentage * 0.75) // 75% of circle

  // Check for reduced motion preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setPrefersReducedMotion(mediaQuery.matches)
    
    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches)
    }
    
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  // Animate the gauge fill and counter
  useEffect(() => {
    if (!animated || prefersReducedMotion) {
      setDisplayScore(clampedScore)
      setStrokeDashOffset(targetOffset)
      return
    }

    // Start from 0
    setDisplayScore(0)
    setStrokeDashOffset(geometry.dashArray) // Start with empty gauge

    // Animate to target score
    const duration = 1000 // 1 second animation
    const startTime = performance.now()

    const animate = () => {
      const elapsed = performance.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      
      // Ease out cubic
      const easedProgress = 1 - Math.pow(1 - progress, 3)
      
      // Update counter
      const currentScore = Math.round(clampedScore * easedProgress)
      setDisplayScore(currentScore)
      
      // Update gauge fill
      const currentOffset = geometry.dashArray * (1 - easedProgress * scorePercentage * 0.75)
      setStrokeDashOffset(currentOffset)

      if (progress < 1) {
        requestAnimationFrame(animate)
      } else {
        setDisplayScore(clampedScore)
        setStrokeDashOffset(targetOffset)
      }
    }

    animationId = requestAnimationFrame(animate)
    return () => {
      if (animationId !== null) {
        cancelAnimationFrame(animationId)
      }
    }
  }, [clampedScore, scorePercentage, animated, prefersReducedMotion, geometry, targetOffset])

  // Generate styles
  const containerStyle: CSSProperties = {
    display: 'inline-flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '0.5rem'
  }

  const svgStyle: CSSProperties = {
    width: size,
    height: size
  }

  return (
    <GaugeErrorBoundary fallback={<div className="score-gauge-static">{clampedScore}</div>}>
      <div className={`score-gauge score-gauge-${severity}`} style={containerStyle} role="meter" aria-label={`Exposure score: ${clampedScore} out of ${maxScore}`} aria-valuenow={clampedScore} aria-valuemin={0} aria-valuemax={maxScore}>
        <svg
          className="score-gauge-svg"
          style={svgStyle}
          viewBox={`0 0 ${size} ${size}`}
          aria-hidden="true"
          focusable="false"
        >
          {/* Background track circle */}
          <circle
            className="gauge-track"
            cx={geometry.center.x}
            cy={geometry.center.y}
            r={geometry.radius}
            fill="none"
            stroke={colors.background}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${geometry.dashArray} ${geometry.circumference}`}
            strokeDashoffset={0}
            transform={`rotate(135 ${geometry.center.x} ${geometry.center.y})`}
          />
          
          {/* Filled arc circle */}
          <circle
            className="gauge-fill"
            cx={geometry.center.x}
            cy={geometry.center.y}
            r={geometry.radius}
            fill="none"
            stroke={colors.stroke}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={geometry.dashArray}
            strokeDashoffset={strokeDashOffset}
            transform={`rotate(135 ${geometry.center.x} ${geometry.center.y})`}
            style={{
              transition: prefersReducedMotion ? 'none' : 'stroke-dashoffset 1s ease-out'
            }}
          />
        </svg>
        
        {/* Center counter */}
        {showCounter && (
          <div className="score-gauge-counter" aria-hidden="true">
            <AnimatedCounter
              value={displayScore}
              duration={animated && !prefersReducedMotion ? 1000 : 0}
              suffix={`/${maxScore}`}
            />
          </div>
        )}
        
        {/* Label */}
        {label && (
          <span className="score-gauge-label">{label}</span>
        )}
      </div>
    </GaugeErrorBoundary>
  )
}

let animationId: number | null = null

export default ScoreGauge



