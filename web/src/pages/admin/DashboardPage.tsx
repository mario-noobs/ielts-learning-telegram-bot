import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

interface DauPoint {
  date: string
  dau: number
  mau: number
  signups: number
}

interface AiUsagePoint {
  date: string
  feature: string
  count: number
}

interface PlanRow {
  plan_id: string
  count: number
}

interface CohortRow {
  cohort_week: string
  signups: number
  retained_d7: number
  retained_d30: number
}

const QUICK_LINKS: { to: string; key: string }[] = [
  { to: '/admin/users', key: 'users.title' },
  { to: '/admin/teams', key: 'teams.title' },
  { to: '/admin/orgs', key: 'orgs.title' },
  { to: '/admin/plans', key: 'plans.title' },
  { to: '/admin/flags', key: 'flags.title' },
  { to: '/admin/audit', key: 'audit.title' },
]

export default function DashboardPage() {
  const { t } = useTranslation('admin')

  const [dau, setDau] = useState<DauPoint[] | null>(null)
  const [ai, setAi] = useState<AiUsagePoint[] | null>(null)
  const [plans, setPlans] = useState<PlanRow[] | null>(null)
  const [cohorts, setCohorts] = useState<CohortRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    Promise.all([
      apiFetch<DauPoint[]>('/api/v1/admin/metrics/dau?days=30'),
      apiFetch<AiUsagePoint[]>('/api/v1/admin/metrics/ai-usage?days=30'),
      apiFetch<PlanRow[]>('/api/v1/admin/metrics/plans'),
      apiFetch<CohortRow[]>('/api/v1/admin/metrics/cohorts?weeks=8'),
    ])
      .then(([d, a, p, c]) => {
        if (cancelled) return
        setDau(d)
        setAi(a)
        setPlans(p)
        setCohorts(c)
      })
      .catch(() => {
        if (!cancelled) setError(t('common.error'))
      })
    return () => {
      cancelled = true
    }
  }, [t])

  return (
    <div className="px-4 md:px-6 py-6 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t('dashboard.title')}</h1>
          <p className="text-muted-fg text-sm">{t('dashboard.subtitle')}</p>
        </div>
        <nav className="flex flex-wrap gap-3 text-sm">
          {QUICK_LINKS.map((l) => (
            <Link key={l.to} to={l.to} className="text-primary underline">
              {t(l.key)}
            </Link>
          ))}
        </nav>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      <section className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="text-lg font-semibold mb-3">
          {t('dashboard.dau.title')}
        </h2>
        <DauChart points={dau} />
      </section>

      <section className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="text-lg font-semibold mb-3">
          {t('dashboard.aiUsage.title')}
        </h2>
        <AiUsageChart points={ai} />
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <section className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="text-lg font-semibold mb-3">
            {t('dashboard.plans.title')}
          </h2>
          <PlanBars rows={plans} />
        </section>
        <section className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="text-lg font-semibold mb-3">
            {t('dashboard.cohorts.title')}
          </h2>
          <CohortTable rows={cohorts} />
        </section>
      </div>
    </div>
  )
}

// ─── DAU / MAU line chart ──────────────────────────────────────────

function DauChart({ points }: { points: DauPoint[] | null }) {
  const { t } = useTranslation('admin')
  if (points === null) return <p className="text-muted-fg">{t('common.loading')}</p>
  if (points.length === 0) return <p className="text-muted-fg">{t('dashboard.empty')}</p>

  const width = 640
  const height = 200
  const padL = 36
  const padR = 12
  const padT = 8
  const padB = 24
  const n = points.length
  const xStep = (width - padL - padR) / Math.max(1, n - 1)
  const yMax = Math.max(1, ...points.map((p) => p.mau))
  const y = (v: number) =>
    padT + (1 - v / yMax) * (height - padT - padB)
  const path = (key: keyof DauPoint, color: string, w: number) =>
    points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${padL + i * xStep} ${y(Number(p[key]))}`)
      .join(' ') + (color ? '' : '') + (w ? '' : '')

  return (
    <div data-testid="dau-chart">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
           aria-label={t('dashboard.dau.title')}>
        {[0, 0.5, 1].map((f) => (
          <line key={f} x1={padL} x2={width - padR}
                y1={padT + f * (height - padT - padB)}
                y2={padT + f * (height - padT - padB)}
                className="stroke-border" strokeWidth={1} />
        ))}
        <path d={path('mau', '', 1.5)} fill="none"
              stroke="rgb(var(--color-accent))" strokeWidth={1.5} opacity={0.7} />
        <path d={path('dau', '', 2.5)} fill="none"
              stroke="rgb(var(--color-primary))" strokeWidth={2.5} />
        <text x={padL - 4} y={padT + 3} fontSize="9" textAnchor="end"
              className="fill-muted-fg">{yMax}</text>
        <text x={padL - 4} y={height - padB + 3} fontSize="9" textAnchor="end"
              className="fill-muted-fg">0</text>
      </svg>
      <div className="flex flex-wrap gap-3 text-xs mt-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-2 rounded-sm bg-primary" />
          <span>{t('dashboard.dau.legendDau')}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-2 rounded-sm bg-accent opacity-70" />
          <span>{t('dashboard.dau.legendMau')}</span>
        </span>
      </div>
    </div>
  )
}

// ─── AI usage stacked area ─────────────────────────────────────────

function AiUsageChart({ points }: { points: AiUsagePoint[] | null }) {
  const { t } = useTranslation('admin')
  if (points === null) return <p className="text-muted-fg">{t('common.loading')}</p>
  if (points.length === 0) return <p className="text-muted-fg">{t('dashboard.empty')}</p>

  // Pivot into per-date totals + per-feature series.
  const dates = Array.from(new Set(points.map((p) => p.date))).sort()
  const features = Array.from(new Set(points.map((p) => p.feature))).sort()
  const matrix: Record<string, Record<string, number>> = {}
  for (const d of dates) matrix[d] = {}
  for (const p of points) matrix[p.date][p.feature] = p.count

  const width = 640
  const height = 200
  const padL = 36
  const padR = 12
  const padT = 8
  const padB = 24
  const n = dates.length
  const xStep = (width - padL - padR) / Math.max(1, n - 1)
  const totals = dates.map((d) =>
    features.reduce((sum, f) => sum + (matrix[d][f] ?? 0), 0),
  )
  const yMax = Math.max(1, ...totals)
  const y = (v: number) => padT + (1 - v / yMax) * (height - padT - padB)

  const COLORS = [
    'rgb(var(--color-primary))',
    'rgb(var(--color-accent))',
    'rgb(var(--color-warning))',
    'rgb(var(--color-success))',
    'rgb(var(--color-danger))',
  ]

  // Build cumulative bands so we can render stacked areas.
  const cumulative: number[][] = features.map(() => Array(n).fill(0))
  features.forEach((f, fi) => {
    for (let i = 0; i < n; i++) {
      const prev = fi === 0 ? 0 : cumulative[fi - 1][i]
      cumulative[fi][i] = prev + (matrix[dates[i]][f] ?? 0)
    }
  })

  return (
    <div data-testid="ai-usage-chart">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
           aria-label={t('dashboard.aiUsage.title')}>
        {[0, 0.5, 1].map((f) => (
          <line key={f} x1={padL} x2={width - padR}
                y1={padT + f * (height - padT - padB)}
                y2={padT + f * (height - padT - padB)}
                className="stroke-border" strokeWidth={1} />
        ))}
        {features.map((f, fi) => {
          const top = cumulative[fi]
          const bottom = fi === 0 ? Array(n).fill(0) : cumulative[fi - 1]
          const fwd = top
            .map((v, i) => `${i === 0 ? 'M' : 'L'} ${padL + i * xStep} ${y(v)}`)
            .join(' ')
          const back = bottom
            .map((_, i) => `L ${padL + (n - 1 - i) * xStep} ${y(bottom[n - 1 - i])}`)
            .reverse()
            .join(' ')
          return (
            <path key={f} d={`${fwd} ${back} Z`}
                  fill={COLORS[fi % COLORS.length]} fillOpacity={0.65}
                  stroke={COLORS[fi % COLORS.length]} strokeWidth={1} />
          )
        })}
        <text x={padL - 4} y={padT + 3} fontSize="9" textAnchor="end"
              className="fill-muted-fg">{yMax}</text>
        <text x={padL - 4} y={height - padB + 3} fontSize="9" textAnchor="end"
              className="fill-muted-fg">0</text>
      </svg>
      <div className="flex flex-wrap gap-3 text-xs mt-1">
        {features.map((f, fi) => (
          <span key={f} className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-2 rounded-sm"
                  style={{ background: COLORS[fi % COLORS.length], opacity: 0.65 }} />
            <span>{f}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// ─── Plan distribution bar ─────────────────────────────────────────

function PlanBars({ rows }: { rows: PlanRow[] | null }) {
  const { t } = useTranslation('admin')
  if (rows === null) return <p className="text-muted-fg">{t('common.loading')}</p>
  if (rows.length === 0) return <p className="text-muted-fg">{t('dashboard.empty')}</p>
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <div className="space-y-2" data-testid="plan-bars">
      {rows.map((r) => (
        <div key={r.plan_id} className="text-sm">
          <div className="flex justify-between">
            <span>{r.plan_id}</span>
            <span className="tabular-nums text-muted-fg">{r.count}</span>
          </div>
          <div className="h-2 mt-1 rounded bg-surface overflow-hidden">
            <div className="h-full bg-primary"
                 style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Cohort retention table ────────────────────────────────────────

function CohortTable({ rows }: { rows: CohortRow[] | null }) {
  const { t } = useTranslation('admin')
  if (rows === null) return <p className="text-muted-fg">{t('common.loading')}</p>
  if (rows.length === 0) return <p className="text-muted-fg">{t('dashboard.empty')}</p>
  const pct = (num: number, denom: number) =>
    denom === 0 ? '—' : `${Math.round((num / denom) * 100)}%`
  return (
    <table className="w-full text-sm" data-testid="cohort-table">
      <thead>
        <tr className="text-left border-b border-border">
          <th className="py-1.5">{t('dashboard.cohorts.week')}</th>
          <th className="py-1.5 text-right">{t('dashboard.cohorts.signups')}</th>
          <th className="py-1.5 text-right">{t('dashboard.cohorts.d7')}</th>
          <th className="py-1.5 text-right">{t('dashboard.cohorts.d30')}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.cohort_week} className="border-b border-border last:border-0">
            <td className="py-1.5">{r.cohort_week}</td>
            <td className="py-1.5 text-right tabular-nums">{r.signups}</td>
            <td className="py-1.5 text-right tabular-nums">
              {pct(r.retained_d7, r.signups)}
            </td>
            <td className="py-1.5 text-right tabular-nums">
              {pct(r.retained_d30, r.signups)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
