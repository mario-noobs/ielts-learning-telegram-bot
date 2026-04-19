import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Icon from './Icon'
import { apiFetch } from '../lib/api'
import {
  SUPPORTED_LOCALES,
  SupportedLocale,
  currentLocale,
  setLocale,
} from '../lib/i18n'

const LABELS: Record<SupportedLocale, string> = {
  en: 'English',
  vi: 'Tiếng Việt',
}

interface Props {
  /** Persist to the server profile when the user is signed in. */
  persistToServer?: boolean
  /** Layout hint — controls the button label visibility. */
  variant?: 'icon' | 'compact'
  className?: string
}

export default function LanguageSwitcher({
  persistToServer = false,
  variant = 'icon',
  className = '',
}: Props) {
  const { t } = useTranslation('common')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState<SupportedLocale>(currentLocale())
  const menuRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  // Keep local "active" in sync with runtime language changes from any
  // source (profile load, direct localStorage edit, etc.).
  useEffect(() => {
    const handler = () => setActive(currentLocale())
    import('i18next').then(({ default: i18n }) => {
      i18n.on('languageChanged', handler)
    })
    return () => {
      import('i18next').then(({ default: i18n }) => {
        i18n.off('languageChanged', handler)
      })
    }
  }, [])

  // Close on outside click + Escape.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!menuRef.current) return
      if (!menuRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const choose = async (code: SupportedLocale) => {
    setOpen(false)
    if (code === active) return
    setActive(code)
    await setLocale(code)
    if (persistToServer) {
      // Fire-and-forget — switcher UX shouldn't wait on a network round-trip.
      apiFetch('/api/v1/me', {
        method: 'PATCH',
        body: JSON.stringify({ preferred_locale: code }),
      }).catch(() => {
        // Silent — localStorage fallback still has the choice.
      })
    }
    buttonRef.current?.focus()
  }

  const label = t('nav.language', { defaultValue: 'Language' })

  return (
    <div ref={menuRef} className={`relative ${className}`}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-raised px-2.5 py-1.5 text-sm font-medium text-fg hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <Icon name="Globe" size="sm" variant="muted" />
        {variant === 'compact' && (
          <span className="hidden sm:inline">{LABELS[active]}</span>
        )}
        <span className="text-xs font-semibold uppercase tracking-wide">
          {active}
        </span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label={label}
          className="absolute right-0 z-50 mt-1 min-w-[160px] overflow-hidden rounded-lg border border-border bg-surface-raised shadow-lg"
        >
          {SUPPORTED_LOCALES.map((code) => {
            const isActive = code === active
            return (
              <button
                key={code}
                role="menuitemradio"
                aria-checked={isActive}
                aria-current={isActive ? 'true' : undefined}
                onClick={() => void choose(code)}
                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-sm ${
                  isActive
                    ? 'bg-primary/10 font-semibold text-primary'
                    : 'text-fg hover:bg-surface'
                }`}
              >
                <span>{LABELS[code]}</span>
                {isActive && <Icon name="Check" size="sm" variant="primary" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
