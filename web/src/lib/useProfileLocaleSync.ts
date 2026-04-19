import { useEffect } from 'react'
import { apiFetch } from './api'
import {
  SUPPORTED_LOCALES,
  SupportedLocale,
  currentLocale,
  setLocale,
} from './i18n'

interface MeResponse {
  preferred_locale?: SupportedLocale | null
}

/**
 * Load-time precedence: profile > localStorage > navigator > EN default.
 *
 * i18next's detector already handles the last three. This hook covers
 * the first — once the user is signed in, fetch /me and if the profile
 * has a saved `preferred_locale`, apply it and mirror to localStorage.
 * Fires once per mount (AppShell), intentionally not tied to every
 * navigation.
 */
export function useProfileLocaleSync(signedIn: boolean): void {
  useEffect(() => {
    if (!signedIn) return
    let cancelled = false
    apiFetch<MeResponse>('/api/v1/me')
      .then((me) => {
        if (cancelled) return
        const code = me.preferred_locale
        if (
          code &&
          (SUPPORTED_LOCALES as readonly string[]).includes(code) &&
          code !== currentLocale()
        ) {
          void setLocale(code as SupportedLocale)
        }
      })
      .catch(() => {
        // Profile fetch failure — keep whatever the detector picked.
      })
    return () => {
      cancelled = true
    }
  }, [signedIn])
}
