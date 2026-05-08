import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Icon from './Icon'
import { track } from '../lib/analytics'
import { useMyAiUsage } from '../lib/useMyAiUsage'

const DISMISS_KEY = 'quota.banner.dismissed'

/** Routes where the AI usage widget already lives — banner would duplicate. */
const SUPPRESSED_PATHS = new Set<string>(['/', '/settings/usage'])

function formatRelativeReset(resetAt: string): string {
  const target = new Date(resetAt).getTime()
  const now = Date.now()
  const diffMs = Math.max(0, target - now)
  if (diffMs === 0) return '0m'
  const totalMin = Math.floor(diffMs / 60_000)
  const hours = Math.floor(totalMin / 60)
  const minutes = totalMin % 60
  if (hours === 0) return `${minutes}m`
  return `${hours}h ${minutes}m`
}

/**
 * Quota-aware threshold banner (US-M13.3).
 *
 * Renders only when `used / quota_daily >= 0.8 && < 1.0` and the user is on
 * a route that doesn't already show the AI usage widget (`/` Dashboard,
 * `/settings/usage` future Settings tab).
 *
 * Dismissible per session via `sessionStorage` — the banner reappears on
 * the next session if the user is still ≥80%, since quota is time-sensitive.
 */
export default function UpgradeBanner() {
  const { t } = useTranslation('dashboard')
  const { pathname } = useLocation()
  const { data } = useMyAiUsage()
  const [dismissed, setDismissed] = useState<boolean | null>(null)
  const [viewedTracked, setViewedTracked] = useState(false)

  useEffect(() => {
    try {
      setDismissed(sessionStorage.getItem(DISMISS_KEY) === '1')
    } catch {
      setDismissed(false)
    }
  }, [])

  const handleDismiss = () => {
    try {
      sessionStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* private mode — dismiss this session only via state */
    }
    setDismissed(true)
  }

  const handleCta = () => {
    track('quota.banner.cta_clicked')
  }

  // Suppress on routes that already show the widget.
  if (SUPPRESSED_PATHS.has(pathname)) return null
  if (dismissed !== false) return null
  if (!data) return null

  const cap = Math.max(0, data.quota_daily)
  if (cap === 0) return null
  const used = Math.min(data.used_today, cap)
  const ratio = used / cap

  // Only render in the warn-80% band — below 80% no banner; at 100% the
  // modal takes over (fired from the global 429 path).
  if (ratio < 0.8 || ratio >= 1) return null

  if (!viewedTracked) {
    track('quota.banner.viewed', { used, cap })
    setViewedTracked(true)
  }

  const remaining = formatRelativeReset(data.reset_at)

  return (
    <div
      role="region"
      aria-label={t('aiUsage.banner.warn80.title')}
      className="relative border-b border-warning/30 bg-warning/10 px-4 py-2.5 md:px-6"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <Icon name="Sparkles" size="sm" variant="primary" className="hidden sm:block" />
          <p className="min-w-0 truncate text-sm text-fg">
            <span className="font-semibold">{t('aiUsage.banner.warn80.title')}</span>
            <span className="mx-1.5 text-muted-fg">·</span>
            <span className="text-muted-fg">
              {t('aiUsage.banner.warn80.body', {
                used,
                plan_quota: cap,
                remaining,
              })}
            </span>
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Link
            to="/pricing"
            onClick={handleCta}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-fg transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {t('aiUsage.banner.warn80.cta')}
          </Link>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label={t('aiUsage.banner.warn80.title')}
            className="rounded-lg p-1.5 text-muted-fg transition-colors hover:bg-surface hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Icon name="X" size="sm" />
          </button>
        </div>
      </div>
    </div>
  )
}
