import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import AiUsageChart, {
  type AiUsagePoint,
} from '../../components/AiUsageChart'
import Pagination from '../../components/Pagination'
import { useProfile } from '../../contexts/AuthContext'
import { apiFetch } from '../../lib/api'
import { localizeError } from '../../lib/apiError'

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

const PAGE_SIZE = 10

/**
 * `/settings/usage` (US-M13.4) — per-user AI usage page.
 *
 * Layout (top-to-bottom):
 *   1. Today summary card (per-feature breakdown always expanded).
 *   2. 30-day stacked-area chart (reuses the admin SVG component).
 *   3. "vs prev 7d" delta line.
 *   4. Plan-vs-override callout (only when `quota_override` is set).
 *   5. Paginated daily-history table.
 */
export default function UsagePage() {
  const { t } = useTranslation('usage')
  const profile = useProfile()
  const [today, setToday] = useState<MeAiUsage | null>(null)
  const [history, setHistory] = useState<AiUsagePoint[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    setError(null)
    Promise.all([
      apiFetch<MeAiUsage>('/api/v1/me/ai-usage'),
      apiFetch<AiUsagePoint[]>('/api/v1/me/ai-usage/history?days=30'),
    ])
      .then(([t1, h]) => {
        if (cancelled) return
        setToday(t1)
        setHistory(h)
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(localizeError(e) || 'error')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-6">
      <div className="text-sm">
        <Link to="/settings" className="text-primary underline">
          ← {t('page.title')}
        </Link>
      </div>
      <header>
        <h1 className="text-2xl font-bold text-fg">{t('page.title')}</h1>
        <p className="text-sm text-muted-fg mt-1">{t('page.subtitle')}</p>
      </header>

      {error && (
        <div
          role="alert"
          className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger"
        >
          {error}
        </div>
      )}

      <TodaySummary data={today} />

      <ChartCard
        title={t('page.last30Days')}
        history={history}
        cap={today?.quota_daily ?? 0}
      />

      {profile && profile.quota_override != null && (
        <div
          data-testid="usage-override-callout"
          className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-fg"
        >
          {t('page.override.notice', { cap: profile.quota_override })}
        </div>
      )}

      <HistoryTable
        history={history}
        cap={today?.quota_daily ?? 0}
        page={page}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  )
}

// ─── Today summary (always-expanded breakdown) ────────────────────────

function TodaySummary({ data }: { data: MeAiUsage | null }) {
  const { t } = useTranslation(['usage', 'dashboard'])
  if (data === null) {
    return (
      <section
        className="rounded-2xl border border-border bg-surface-raised p-4"
        data-testid="usage-today-loading"
      >
        <div className="h-4 w-1/3 animate-pulse rounded bg-surface" />
        <div className="mt-3 h-2 w-full animate-pulse rounded bg-surface" />
      </section>
    )
  }
  const cap = Math.max(0, data.quota_daily)
  const used = Math.min(data.used_today, cap || data.used_today)
  const pct = cap > 0 ? Math.min(100, Math.round((used / cap) * 100)) : 0
  return (
    <section
      data-testid="usage-today-card"
      aria-label={t('page.today')}
      className="rounded-2xl border border-border bg-surface-raised p-4 space-y-3"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">{t('page.today')}</h2>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-fg">
          {data.plan}
        </span>
      </div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium tabular-nums">
          {t('dashboard:aiUsage.usedOfQuota', { used, plan_quota: cap })}
        </span>
        <span className="tabular-nums text-muted-fg">{pct}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-surface"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full bg-success" style={{ width: `${pct}%` }} />
      </div>
      {data.by_feature.length > 0 && (
        <ul
          className="mt-2 space-y-1 text-xs text-muted-fg"
          data-testid="usage-today-breakdown"
        >
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
    </section>
  )
}

// ─── 30-day chart card with delta line ────────────────────────────────

function ChartCard({
  title,
  history,
  cap,
}: {
  title: string
  history: AiUsagePoint[] | null
  cap: number
}) {
  const { t } = useTranslation('usage')
  const delta = useMemo(() => computeDelta(history), [history])
  return (
    <section
      data-testid="usage-chart-card"
      className="rounded-2xl border border-border bg-surface-raised p-4 space-y-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        {delta !== null && (
          <span
            data-testid="usage-delta"
            className={`text-xs ${
              delta.direction === 'up' ? 'text-success' : 'text-muted-fg'
            }`}
          >
            {delta.direction === 'up' &&
              t('page.vsLast7Up', { pct: delta.pct })}
            {delta.direction === 'down' &&
              t('page.vsLast7Down', { pct: delta.pct })}
            {delta.direction === 'flat' && t('page.vsLast7Flat')}
          </span>
        )}
      </div>
      <AiUsageChart points={history} ariaLabel={title} />
      {/* Cap is read here for future "% of cap" overlay; reserved. */}
      <span className="sr-only" data-testid="usage-cap">
        {cap}
      </span>
    </section>
  )
}

interface Delta {
  pct: number
  direction: 'up' | 'down' | 'flat'
}

/**
 * Sum of last 7 days vs days 8..14 expressed as a signed percentage.
 * Returns `null` while loading; `flat` when the prior window is zero or
 * the change is exactly zero (we don't want to shame the user with a
 * misleading "+∞%" jump out of an empty baseline).
 */
function computeDelta(history: AiUsagePoint[] | null): Delta | null {
  if (history === null) return null
  if (history.length === 0) return { pct: 0, direction: 'flat' }
  // Group by date → total. Sort dates desc.
  const totals = new Map<string, number>()
  for (const p of history) {
    totals.set(p.date, (totals.get(p.date) ?? 0) + p.count)
  }
  const datesDesc = Array.from(totals.keys()).sort().reverse()
  const last7 = datesDesc.slice(0, 7).reduce((s, d) => s + (totals.get(d) ?? 0), 0)
  const prev7 = datesDesc
    .slice(7, 14)
    .reduce((s, d) => s + (totals.get(d) ?? 0), 0)
  if (prev7 === 0) return { pct: 0, direction: 'flat' }
  const diff = last7 - prev7
  const pct = Math.round((Math.abs(diff) / prev7) * 100)
  if (diff === 0 || pct === 0) return { pct: 0, direction: 'flat' }
  return { pct, direction: diff > 0 ? 'up' : 'down' }
}

// ─── Paginated daily history table ────────────────────────────────────

function HistoryTable({
  history,
  cap,
  page,
  onPrev,
  onNext,
}: {
  history: AiUsagePoint[] | null
  cap: number
  page: number
  onPrev: () => void
  onNext: () => void
}) {
  const { t } = useTranslation('usage')

  const { rows, features, totalPages } = useMemo(() => {
    if (history === null || history.length === 0) {
      return { rows: [], features: [], totalPages: 1 }
    }
    const featSet = new Set<string>()
    const byDate = new Map<string, Record<string, number>>()
    for (const p of history) {
      featSet.add(p.feature)
      const row = byDate.get(p.date) ?? {}
      row[p.feature] = (row[p.feature] ?? 0) + p.count
      byDate.set(p.date, row)
    }
    const featuresList = Array.from(featSet).sort()
    const allRows = Array.from(byDate.entries())
      .map(([date, row]) => ({
        date,
        row,
        total: Object.values(row).reduce((s, n) => s + n, 0),
      }))
      .sort((a, b) => (a.date < b.date ? 1 : -1))
    return {
      rows: allRows,
      features: featuresList,
      totalPages: Math.max(1, Math.ceil(allRows.length / PAGE_SIZE)),
    }
  }, [history])

  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (history === null) {
    return (
      <section
        className="rounded-2xl border border-border bg-surface-raised p-4"
        data-testid="usage-history-loading"
      >
        <div className="h-4 w-1/3 animate-pulse rounded bg-surface" />
      </section>
    )
  }

  if (rows.length === 0) {
    return (
      <section
        className="rounded-2xl border border-border bg-surface-raised p-4"
        data-testid="usage-history-empty"
      >
        <h2 className="text-sm font-semibold">{t('page.history.title')}</h2>
        <p className="text-sm text-muted-fg mt-2">{t('page.history.empty')}</p>
      </section>
    )
  }

  return (
    <section
      data-testid="usage-history-card"
      className="rounded-2xl border border-border bg-surface-raised p-4 space-y-3"
    >
      <h2 className="text-sm font-semibold">{t('page.history.title')}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="usage-history-table">
          <thead>
            <tr className="text-left border-b border-border">
              <th className="py-1.5">{t('page.history.col.date')}</th>
              <th className="py-1.5 text-right">{t('page.history.col.total')}</th>
              {features.map((f) => (
                <th key={f} className="py-1.5 text-right">
                  {f}
                </th>
              ))}
              <th className="py-1.5 text-right">{t('page.history.col.pctCap')}</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => {
              const pctCap =
                cap > 0 ? Math.min(999, Math.round((r.total / cap) * 100)) : 0
              return (
                <tr
                  key={r.date}
                  className="border-b border-border last:border-0"
                >
                  <td className="py-1.5">{r.date}</td>
                  <td className="py-1.5 text-right tabular-nums">{r.total}</td>
                  {features.map((f) => (
                    <td
                      key={f}
                      className="py-1.5 text-right tabular-nums text-muted-fg"
                    >
                      {r.row[f] ?? 0}
                    </td>
                  ))}
                  <td className="py-1.5 text-right tabular-nums text-muted-fg">
                    {cap > 0 ? `${pctCap}%` : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPrev={onPrev}
          onNext={onNext}
        />
      )}
    </section>
  )
}
