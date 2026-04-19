import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import Icon from '../../components/Icon'

type WordItem = {
  id: string
  word: string
  added_at: string | null
  meaning_vi?: string | null
}

type WordListResponse = {
  items: WordItem[]
  next_cursor: string | null
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('vi-VN', { day: 'numeric', month: 'short' })
}

export default function RecentContent() {
  const [items, setItems] = useState<WordItem[] | null>(null)

  useEffect(() => {
    apiFetch<WordListResponse>('/api/v1/vocabulary?limit=3')
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
  }, [])

  // Hide entirely if loading failed or list is empty (AC5 — no empty-state nag).
  if (items === null || items.length === 0) return null

  return (
    <section aria-labelledby="recent-content-heading">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="recent-content-heading" className="font-semibold text-fg">
          Từ vừa học gần đây
        </h2>
        <Link
          to="/vocab"
          className="text-sm text-primary hover:text-primary-hover focus-visible:outline-none focus-visible:underline"
        >
          Xem tất cả →
        </Link>
      </div>

      <ul className="rounded-2xl border border-border bg-surface-raised divide-y divide-border overflow-hidden">
        {items.map((w) => (
          <li key={w.id}>
            <Link
              to={`/vocab/${encodeURIComponent(w.id)}`}
              className="flex items-center gap-3 p-4 transition-colors hover:bg-surface focus-visible:bg-surface focus-visible:outline-none"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon name="BookOpen" size="md" variant="primary" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-fg">{w.word}</p>
                {w.meaning_vi && (
                  <p className="truncate text-sm text-muted-fg">{w.meaning_vi}</p>
                )}
              </div>
              <div className="shrink-0 text-xs text-muted-fg">
                {formatDate(w.added_at)}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
