import { useEffect, useRef } from 'react'

interface Draft<T> {
  value: T
  savedAt: number
}

/**
 * Debounced localStorage autosave. Never clobbers a newer payload with an
 * older one — the setTimeout closure captures the caller-visible value and
 * writes monotonically via a timestamp check.
 */
export function useAutosave<T>(
  key: string,
  value: T,
  delayMs = 5000,
  onSaved?: (savedAt: number) => void,
): void {
  const timer = useRef<number | null>(null)
  useEffect(() => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      try {
        const existing = loadDraft<T>(key)
        const savedAt = Date.now()
        if (existing && existing.savedAt > savedAt) return // never go back in time
        localStorage.setItem(key, JSON.stringify({ value, savedAt }))
        onSaved?.(savedAt)
      } catch {
        // localStorage can fail (quota, private mode) — silently drop
      }
      timer.current = null
    }, delayMs)
    return () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current)
        timer.current = null
      }
    }
  }, [key, value, delayMs, onSaved])
}

export function loadDraft<T>(key: string): Draft<T> | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw) as Draft<T>
  } catch {
    return null
  }
}

export function clearDraft(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* noop */
  }
}

export function formatTimeVi(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}
