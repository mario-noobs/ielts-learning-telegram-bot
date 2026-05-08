import { useTranslation } from 'react-i18next'

export interface AiUsagePoint {
  date: string
  feature: string
  count: number
}

interface Props {
  points: AiUsagePoint[] | null
  /** Optional aria-label override. Defaults to `admin:dashboard.aiUsage.title`. */
  ariaLabel?: string
}

const COLORS = [
  'rgb(var(--color-primary))',
  'rgb(var(--color-accent))',
  'rgb(var(--color-warning))',
  'rgb(var(--color-success))',
  'rgb(var(--color-danger))',
]

/**
 * Hand-rolled stacked-area SVG chart for per-day per-feature AI usage
 * (US-M11.5 admin dashboard, lifted to a shared module in US-M13.4 so
 * the user-facing ``/settings/usage`` page can render the same chart
 * without pulling in a chart library).
 *
 * Loading state when `points === null`; empty state when `points.length === 0`.
 */
export default function AiUsageChart({ points, ariaLabel }: Props) {
  const { t } = useTranslation('admin')
  const label = ariaLabel ?? t('dashboard.aiUsage.title')

  if (points === null) return <p className="text-muted-fg">{t('common.loading')}</p>
  if (points.length === 0)
    return <p className="text-muted-fg">{t('dashboard.empty')}</p>

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
           aria-label={label}>
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
