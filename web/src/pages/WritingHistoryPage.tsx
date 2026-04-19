import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import EmptyState from '../components/EmptyState'
import { WritingHistoryItem } from '../lib/writing'

function BandTrend({
  items,
  heading,
}: {
  items: WritingHistoryItem[]
  heading: string
}) {
  const points = useMemo(() => {
    const sorted = [...items]
      .filter((i) => i.created_at)
      .sort((a, b) => Date.parse(a.created_at!) - Date.parse(b.created_at!))
    return sorted
  }, [items])

  if (points.length < 2) return null

  const width = 600
  const height = 120
  const padX = 20
  const padY = 16
  const minBand = Math.max(0, Math.min(...points.map((p) => p.overall_band)) - 0.5)
  const maxBand = Math.min(9, Math.max(...points.map((p) => p.overall_band)) + 0.5)
  const range = Math.max(0.5, maxBand - minBand)

  const coords = points.map((p, i) => {
    const x = padX + (i / (points.length - 1)) * (width - 2 * padX)
    const y = padY + (1 - (p.overall_band - minBand) / range) * (height - 2 * padY)
    return { x, y, band: p.overall_band, id: p.id }
  })

  const path = coords.map((c, i) => (i === 0 ? 'M' : 'L') + c.x + ' ' + c.y).join(' ')

  return (
    <div className="bg-surface-raised rounded-xl shadow-sm p-5">
      <h2 className="font-semibold text-fg mb-3">{heading}</h2>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto text-primary">
        <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
        {coords.map((c, i) => (
          <g key={i}>
            <circle cx={c.x} cy={c.y} r="4" fill="currentColor" />
            <text
              x={c.x}
              y={c.y - 8}
              fontSize="10"
              textAnchor="middle"
              className="fill-fg"
            >
              {c.band.toFixed(1)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function formatDate(iso: string | null, lang: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const locale = lang.startsWith('vi') ? 'vi-VN' : 'en-GB'
  return d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function TaskBadge({ type }: { type: string }) {
  return (
    <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
      {type === 'task1' ? 'Task 1' : 'Task 2'}
    </span>
  )
}

export default function WritingHistoryPage() {
  const { t, i18n } = useTranslation(['writing', 'common'])
  const [items, setItems] = useState<WritingHistoryItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ items: WritingHistoryItem[] }>('/api/v1/writing/history')
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-end">
        <Link
          to="/write"
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          {t('writing:history.newEssayLink')}
        </Link>
      </div>

      <h1 className="text-2xl font-bold">{t('writing:history.heading')}</h1>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-danger text-sm">
          {error}
        </div>
      )}

      {items === null ? (
        <div className="animate-pulse space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 bg-border rounded-lg" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          illustration="empty-writing"
          title={t('writing:history.empty.title')}
          description={t('writing:history.empty.description')}
          primaryAction={{ label: t('writing:history.empty.cta'), to: '/write' }}
        />
      ) : (
        <>
          <BandTrend items={items} heading={t('writing:history.bandTrendHeading')} />
          <div className="space-y-2">
            {items.map((it) => (
              <Link
                key={it.id}
                to={`/write/${it.id}`}
                className="bg-surface-raised rounded-lg p-4 flex items-center justify-between hover:shadow-sm transition"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <TaskBadge type={it.task_type} />
                    {it.original_id && (
                      <span className="text-xs bg-warning/10 text-warning px-2 py-0.5 rounded">
                        {t('writing:history.revisedBadge')}
                      </span>
                    )}
                    <span className="text-xs text-muted-fg">{formatDate(it.created_at, i18n.language)}</span>
                  </div>
                  <p className="text-sm text-fg truncate">{it.prompt_preview}</p>
                  <p className="text-xs text-muted-fg mt-0.5">
                    {t('writing:wordCount', { count: it.word_count })}
                  </p>
                </div>
                <div className="text-2xl font-bold text-primary ml-4">
                  {it.overall_band.toFixed(1)}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
