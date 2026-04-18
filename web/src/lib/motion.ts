import { useEffect, useState } from 'react'

/**
 * Returns `true` when the user prefers reduced motion. Components should
 * gate JS-driven animations (typewriter, SVG stroke-dashoffset tweens) on
 * this value. CSS transitions already use the `@media (prefers-reduced-motion)`
 * rule in tokens.css, so pure-CSS animations do not need this hook.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window === 'undefined'
      ? false
      : window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  )

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return reduced
}
