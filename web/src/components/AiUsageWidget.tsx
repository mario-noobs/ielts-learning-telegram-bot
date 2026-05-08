import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon from './Icon'
import { apiFetch } from '../lib/api'

interface FeaturePoint {
  feature: string
  count: number
}

interface MeAiUsage {
  plan: string
  quota_daily: number
  used_today: number
  by_feature: FeaturePoint[]
  reset_at: string
}

const PAID_PLANS = new Set(['personal_pro', 'team_member', 'org_member'])

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
 * "AI usage today" widget for the consumer dashboard (US-M13.1).
 *
 * Reads `GET /api/v1/me/ai-usage` once on mount. Per the locked product
 * rule (`docs/quota.md`), this only reflects user-initiated AI calls;
 * cron-served content (daily vocab, coaching tips) doesn't count.
 *
 * Saturated state (used >= cap) renders a striped red bar so the
 * limit-reached state is not color-only (WCAG 1.4.1).
 */
export default function AiUsageWidget() {
  const { t } = useTranslation('dashboard')
  const [data, setData] = useState<MeAiUsage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showFeatures, setShowFeatures] = useState(false)
  const [, forceTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    apiFetch<MeAiUsage>('/api/v1/me/ai-usage')
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch(() => {
        if (!cancelled) setError(t('aiUsage.error'))
      })
    return () => {
      cancelled = true
    }
  }, [t])

  // Re-render every 60s so the relative reset countdown updates.
  useEffect(() => {
    const id = window.setInterval(() => forceTick((n) => n + 1), 60_000)
    return () => window.clearInterval(id)
  }, [])

  const computed = useMemo(() => {
    if (!data) return null
    const cap = Math.max(0, data.quota_daily)
    const used = Math.min(data.used_today, cap || data.used_today)
    const pct = cap > 0 ? Math.min(100, Math.round((used / cap) * 100)) : 0
    const saturated = cap > 0 && used >= cap
    const warning = !saturated && cap > 0 && used / cap >= 0.8
    return { cap, used, pct, saturated, warning }
  }, [data])

  if (error) {
    return (
      <section
        aria-label={t('aiUsage.title')}
        className="rounded-2xl border border-border bg-surface-raised p-4"
      >
        <p className="text-sm text-muted-fg">{error}</p>
      </section>
    )
  }

  if (!data || !computed) {
    return (
      <section
        aria-label={t('aiUsage.title')}
        className="rounded-2xl border border-border bg-surface-raised p-4"
        data-testid="ai-usage-loading"
      >
        <div className="h-4 w-1/3 animate-pulse rounded bg-surface" />
        <div className="mt-3 h-2 w-full animate-pulse rounded bg-surface" />
      </section>
    )
  }

  const { cap, used, pct, saturated, warning } = computed
  const isFree = !PAID_PLANS.has(data.plan)
  const barColor = saturated
    ? 'bg-danger'
    : warning
      ? 'bg-warning'
      : 'bg-success'
  const stripes = saturated
    ? 'bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,rgba(255,255,255,0.25)_4px,rgba(255,255,255,0.25)_8px)]'
    : ''
  const empty = used === 0 && !saturated

  return (
    <section
      aria-label={t('aiUsage.title')}
      className="rounded-2xl border border-border bg-surface-raised p-4 space-y-3"
      data-testid="ai-usage-widget"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">
          {saturated ? t('aiUsage.saturated.title') : t('aiUsage.title')}
        </h2>
        <Link
          to="/pricing"
          className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-fg hover:text-fg"
        >
          {data.plan}
        </Link>
      </div>

      <div className="space-y-1">
        <div className="flex items-baseline justify-between gap-2 text-sm">
          <span className="font-medium tabular-nums">
            {empty
              ? t('aiUsage.empty')
              : t('aiUsage.usedOfQuota', { used, plan_quota: cap })}
          </span>
          <span className="tabular-nums text-muted-fg">{pct}%</span>
        </div>
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-surface"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t('aiUsage.barAriaLabel', {
            used,
            plan_quota: cap,
            pct,
          })}
        >
          <div
            className={`h-full ${barColor} ${stripes}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {data.by_feature.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowFeatures((v) => !v)}
            aria-expanded={showFeatures}
            className="flex items-center gap-1 text-xs text-muted-fg hover:text-fg"
          >
            <Icon
              name="ChevronRight"
              size="sm"
              variant="muted"
              className={`transition-transform ${
                showFeatures ? 'rotate-90' : ''
              }`}
            />
            {t('aiUsage.breakdownToggle')}
          </button>
          {showFeatures && (
            <ul className="mt-2 space-y-1 text-xs text-muted-fg">
              {data.by_feature.map((f) => (
                <li
                  key={f.feature}
                  className="flex items-center justify-between"
                >
                  <span>{f.feature}</span>
                  <span className="tabular-nums">{f.count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 pt-1 text-xs">
        <span className="text-muted-fg">
          {t('aiUsage.resetIn', { remaining: formatRelativeReset(data.reset_at) })}
        </span>
        {isFree && (
          <Link
            to="/pricing"
            className="font-medium text-primary hover:underline"
          >
            {t('aiUsage.upgrade')}
          </Link>
        )}
      </div>
    </section>
  )
}
