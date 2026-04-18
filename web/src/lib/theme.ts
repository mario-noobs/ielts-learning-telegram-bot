import { useEffect, useState, useCallback } from 'react'

export type ThemePref = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'ui.theme'

function storedPref(): ThemePref {
  if (typeof window === 'undefined') return 'system'
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw === 'light' || raw === 'dark' ? raw : 'system'
}

function resolvedTheme(pref: ThemePref): 'light' | 'dark' {
  if (pref === 'light' || pref === 'dark') return pref
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

/**
 * Call once at app boot (before first paint) to prevent FOUC.
 * No-op on SSR.
 */
export function initTheme(): void {
  if (typeof document === 'undefined') return
  applyTheme(resolvedTheme(storedPref()))
}

export function useTheme(): {
  pref: ThemePref
  resolved: 'light' | 'dark'
  setPref: (p: ThemePref) => void
} {
  const [pref, setPrefState] = useState<ThemePref>(() => storedPref())
  const [resolved, setResolved] = useState<'light' | 'dark'>(() => resolvedTheme(storedPref()))

  // Apply whenever pref changes
  useEffect(() => {
    const r = resolvedTheme(pref)
    setResolved(r)
    applyTheme(r)
  }, [pref])

  // React to OS preference changes when pref is "system"
  useEffect(() => {
    if (pref !== 'system' || typeof window === 'undefined') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const r = resolvedTheme('system')
      setResolved(r)
      applyTheme(r)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [pref])

  const setPref = useCallback((p: ThemePref) => {
    if (p === 'system') localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, p)
    setPrefState(p)
  }, [])

  return { pref, resolved, setPref }
}
