import i18n from 'i18next'
import HttpBackend from 'i18next-http-backend'
import LanguageDetector from 'i18next-browser-languagedetector'
import ICU from 'i18next-icu'
import { initReactI18next } from 'react-i18next'

export const SUPPORTED_LOCALES = ['en', 'vi'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

export const DEFAULT_LOCALE: SupportedLocale = 'en'

// Namespaces split per feature area so route navigation only pulls the
// bundle it needs (US-M7.1 AC2). Add a namespace here AND create
// matching public/locales/{lng}/{ns}.json files before using it.
export const NAMESPACES = [
  'common',
  'dashboard',
  'landing',
  'settings',
] as const

const LANG_STORAGE_KEY = 'ieltscoach_lang_v1'

/**
 * Initialise i18next.
 *
 * - Default and fallback locale: EN (project decision — web app is
 *   EN-first; VN is a selectable alternate).
 * - Detection order: user's explicit choice in localStorage → browser
 *   → default. The detector never overrides an existing choice.
 * - Bundles are lazy-loaded via HTTP backend from /locales/{lng}/{ns}.json.
 *   Vite copies /public/locales to /dist/locales at build time.
 * - Missing keys log a warning in dev (saveMissing=true); Sentry wiring
 *   is attached in main.tsx when Sentry loads.
 */
void i18n
  .use(ICU)
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: SUPPORTED_LOCALES as unknown as string[],
    load: 'languageOnly',
    nonExplicitSupportedLngs: true,
    ns: NAMESPACES as unknown as string[],
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: LANG_STORAGE_KEY,
      caches: ['localStorage'],
    },
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },
    saveMissing: import.meta.env.DEV,
    missingKeyHandler: (lngs, ns, key) => {
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.warn(`[i18n] missing key: ${lngs.join(',')} / ${ns}:${key}`)
      }
    },
    react: {
      useSuspense: true,
    },
  })

/** Set the active locale and persist to localStorage. */
export function setLocale(locale: SupportedLocale): Promise<unknown> {
  try {
    localStorage.setItem(LANG_STORAGE_KEY, locale)
  } catch {
    // storage blocked — still change the runtime language
  }
  return i18n.changeLanguage(locale)
}

/** Current base locale ('en' | 'vi'), stripped of any region suffix. */
export function currentLocale(): SupportedLocale {
  const raw = (i18n.language || DEFAULT_LOCALE).split('-')[0]
  return (SUPPORTED_LOCALES as readonly string[]).includes(raw)
    ? (raw as SupportedLocale)
    : DEFAULT_LOCALE
}

export default i18n
