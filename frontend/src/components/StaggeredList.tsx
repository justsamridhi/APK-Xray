import { useEffect, useState, useCallback, type ReactNode, type CSSProperties } from 'react'

export type AnimationType = 'fadeUp' | 'slideIn' | 'scaleIn'

export interface StaggeredListProps<T extends { id: string | number }> {
  items: T[]
  children: (item: T, index: number) => ReactNode
  staggerDelay?: number      // Delay between each item (default: 100)
  animationType?: AnimationType
  containerClassName?: string
  itemClassName?: string
  keyExtractor?: (item: T) => string | number
}

/**
 * Maps animation type to CSS class name
 */
function getAnimationClass(type: AnimationType): string {
  switch (type) {
    case 'fadeUp':
      return 'animate-fade-in-up'
    case 'slideIn':
      return 'animate-slide-in'
    case 'scaleIn':
      return 'animate-scale-in'
    default:
      return 'animate-fade-in-up'
  }
}

/**
 * Error boundary wrapper for individual list items
 */
function ItemErrorBoundary({ children, fallback }: { children: ReactNode; fallback?: ReactNode }) {
  const [hasError] = useState(false)

  if (hasError) {
    return fallback || <div className="staggered-item-error">Item unavailable</div>
  }

  return <>{children}</>
}

/**
 * StaggeredList - Renders a list with staggered child reveal animations
 * Uses CSS animation with staggered delays for smooth visual effects
 * Maintains original DOM order for accessibility
 * Respects prefers-reduced-motion accessibility preference
 */
export function StaggeredList<T extends { id: string | number }>({
  items,
  children,
  staggerDelay = 100,
  animationType = 'fadeUp',
  containerClassName = '',
  itemClassName = '',
  keyExtractor
}: StaggeredListProps<T>) {
  const [animatedItems, setAnimatedItems] = useState<Set<string | number>>(new Set())
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

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

  // Trigger animations when items change
  useEffect(() => {
    if (prefersReducedMotion || items.length === 0) {
      // Show all items immediately without animation
      setAnimatedItems(new Set(items.map(item => item.id)))
      return
    }

    // Clear previous animations and start new staggered reveal
    setAnimatedItems(new Set())
    
    items.forEach((item, index) => {
      const delay = index * staggerDelay
      setTimeout(() => {
        setAnimatedItems(prev => new Set(prev).add(item.id))
      }, delay)
    })
  }, [items, staggerDelay, prefersReducedMotion])

  // Generate animation style for staggered delay
  const getItemStyle = useCallback((index: number): CSSProperties => {
    if (prefersReducedMotion) {
      return {}
    }
    return {
      animationDelay: `${index * staggerDelay}ms`
    }
  }, [staggerDelay, prefersReducedMotion])

  // Handle empty state
  if (items.length === 0) {
    return (
      <div className={`staggered-list-empty ${containerClassName}`}>
        No items to display
      </div>
    )
  }

  return (
    <div className={`animate-stagger-children ${containerClassName}`} role="list" aria-label="Staggered list">
      {items.map((item, index) => {
        const key = keyExtractor ? keyExtractor(item) : item.id
        const isAnimated = animatedItems.has(item.id) || prefersReducedMotion
        const animationClass = getAnimationClass(animationType)
        
        return (
          <div
            key={key}
            className={`staggered-item ${animationClass} ${isAnimated ? 'animate' : ''} ${itemClassName}`}
            style={getItemStyle(index)}
            role="listitem"
          >
            <ItemErrorBoundary fallback={<div className="staggered-item-fallback">Item unavailable</div>}>
              {children(item, index)}
            </ItemErrorBoundary>
          </div>
        )
      })}
    </div>
  )
}

export default StaggeredList
