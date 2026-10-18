import type { CSSProperties } from 'react'

export type SkeletonVariant = 'text' | 'title' | 'card' | 'avatar' | 'custom'

export interface LoadingSkeletonProps {
  variant?: SkeletonVariant
  width?: string | number
  height?: string | number
  borderRadius?: string | number
  className?: string
  count?: number // Number of skeleton elements to render
}

/**
 * Gets default dimensions for each skeleton variant
 */
function getVariantDefaults(variant: SkeletonVariant): { width: string | number; height: string | number; borderRadius: string | number } {
  switch (variant) {
    case 'text':
      return { width: '100%', height: '1em', borderRadius: '4px' }
    case 'title':
      return { width: '60%', height: '1.5em', borderRadius: '6px' }
    case 'card':
      return { width: '100%', height: '120px', borderRadius: '12px' }
    case 'avatar':
      return { width: '40px', height: '40px', borderRadius: '50%' }
    case 'custom':
      return { width: '100%', height: '1em', borderRadius: '4px' }
    default:
      return { width: '100%', height: '1em', borderRadius: '4px' }
  }
}

/**
 * Gets CSS class for skeleton variant
 */
function getVariantClass(variant: SkeletonVariant): string {
  switch (variant) {
    case 'text':
      return 'skeleton-text'
    case 'title':
      return 'skeleton-title'
    case 'card':
      return 'skeleton-card'
    case 'avatar':
      return 'skeleton-avatar'
    case 'custom':
      return 'skeleton-custom'
    default:
      return 'skeleton-text'
  }
}

/**
 * LoadingSkeleton - Displays skeleton loading states with shimmer effect
 * Uses CSS shimmer animation that adapts to light/dark themes via CSS variables
 * Renders multiple skeletons for lists when count > 1
 * Respects prefers-reduced-motion accessibility preference
 */
export function LoadingSkeleton({
  variant = 'text',
  width,
  height,
  borderRadius,
  className = '',
  count = 1
}: LoadingSkeletonProps) {
  const defaults = getVariantDefaults(variant)
  const variantClass = getVariantClass(variant)
  
  // Merge provided values with defaults
  const skeletonWidth = width ?? defaults.width
  const skeletonHeight = height ?? defaults.height
  const skeletonBorderRadius = borderRadius ?? defaults.borderRadius

  // Check for reduced motion preference
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setPrefersReducedMotion(mediaQuery.matches)
    
    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches)
    }
    
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  // Generate style object
  const getSkeletonStyle = (): CSSProperties => {
    const baseStyle: CSSProperties = {
      width: skeletonWidth,
      height: skeletonHeight,
      borderRadius: skeletonBorderRadius
    }

    if (prefersReducedMotion) {
      // Static placeholder without animation
      return {
        ...baseStyle,
        backgroundColor: 'var(--surface-muted)'
      }
    }

    return baseStyle
  }

  // Render single skeleton
  const renderSkeleton = (key?: string | number) => (
    <div
      key={key}
      className={`skeleton ${variantClass} ${className}`}
      style={getSkeletonStyle()}
      role="status"
      aria-label="Loading"
      aria-busy="true"
    />
  )

  // Render multiple skeletons for lists
  if (count > 1) {
    return (
      <div className="skeleton-list" role="group" aria-label={`Loading ${count} items`}>
        {Array.from({ length: count }, (_, index) => renderSkeleton(index))}
      </div>
    )
  }

  return renderSkeleton()
}

/**
 * SkeletonCard - Convenience component for card-sized loading placeholder
 */
export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`skeleton-card-wrapper ${className}`}>
      <LoadingSkeleton variant="title" />
      <LoadingSkeleton variant="text" />
      <LoadingSkeleton variant="text" width="80%" />
    </div>
  )
}

/**
 * SkeletonList - Renders a list of skeleton items
 */
export function SkeletonList({ count = 3, className = '' }: { count?: number; className?: string }) {
  return (
    <div className={`skeleton-list-wrapper ${className}`}>
      {Array.from({ length: count }, (_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  )
}

import { useState, useEffect } from 'react'
export default LoadingSkeleton