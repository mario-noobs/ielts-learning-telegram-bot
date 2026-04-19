import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'
import {
  BAND_TIERS,
  PassageSummary,
  listPassages,
} from '../lib/reading'

export default function ReadingHomePage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<PassageSummary[] | null>(null)
  const [band, setBand] = useState<number | null>(null)
  const [topic, setTopic] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState<string | null>(null)

  useEffect(() => {
    listPassages({ band: band ?? undefined, topic: topic || undefined })
      .then((r) => setItems(r.items))
      .catch((e) => setError((e as Error).message))
  }, [band, topic])

  const topics = useMemo(() => {
    if (!items) return []
    return Array.from(new Set(items.map((p) => p.topic))).sort()
  }, [items])

  const start = (passageId: string) => {
    if (starting) return
    setStarting(passageId)
    navigate(`/reading/${encodeURIComponent(passageId)}`)
  }

  return (
    <div className="mx-auto max-w-3xl p-4 space-y-4 md:p-6">
      <header>
        <h1 className="text-2xl font-bold text-fg">Reading Lab</h1>
        <p className="mt-1 text-sm text-muted-fg">
          Chọn một bài đọc theo band mục tiêu. Mỗi phiên kéo dài 20 phút với 13 câu hỏi.
        </p>
      </header>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-fg">Band:</span>
        <button
          onClick={() => setBand(null)}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            band === null
              ? 'bg-primary text-primary-fg'
              : 'bg-surface-raised text-fg border border-border hover:bg-surface'
          }`}
        >
          Tất cả
        </button>
        {BAND_TIERS.map((b) => (
          <button
            key={b}
            onClick={() => setBand(b)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              band === b
                ? 'bg-primary text-primary-fg'
                : 'bg-surface-raised text-fg border border-border hover:bg-surface'
            }`}
          >
            {b.toFixed(1)}
          </button>
        ))}
      </div>

      {topics.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-muted-fg">Chủ đề:</span>
          <button
            onClick={() => setTopic('')}
            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${
              topic === ''
                ? 'bg-primary text-primary-fg'
                : 'bg-surface-raised text-fg border border-border hover:bg-surface'
            }`}
          >
            Tất cả
          </button>
          {topics.map((t) => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${
                topic === t
                  ? 'bg-primary text-primary-fg'
                  : 'bg-surface-raised text-fg border border-border hover:bg-surface'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {items === null ? (
        <div className="space-y-2" aria-hidden="true">
          <div className="h-16 animate-pulse rounded-xl bg-surface" />
          <div className="h-16 animate-pulse rounded-xl bg-surface" />
          <div className="h-16 animate-pulse rounded-xl bg-surface" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          illustration="plan-complete"
          title="Không có bài đọc phù hợp"
          description="Thử đổi band hoặc chủ đề khác."
          primaryAction={{ label: 'Xem tất cả', to: '/reading' }}
        />
      ) : (
        <ul className="space-y-2">
          {items.map((p) => (
            <li key={p.id}>
              <button
                onClick={() => start(p.id)}
                disabled={!!starting}
                className="w-full text-left bg-surface-raised rounded-xl border border-border hover:border-primary/40 hover:shadow-sm p-4 flex items-center gap-3 transition-colors disabled:opacity-50"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon name="FileText" size="md" variant="primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-fg">{p.title}</p>
                  <p className="mt-0.5 text-xs text-muted-fg">
                    <span className="capitalize">{p.topic}</span> · Band {p.band.toFixed(1)} · {p.word_count} từ
                  </p>
                </div>
                <Icon name="ChevronRight" size="md" variant="muted" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="pt-2 text-center text-xs text-muted-fg">
        <Link to="/" className="hover:text-fg">← Dashboard</Link>
      </p>
    </div>
  )
}
