import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'
import { apiFetch } from '../lib/api'
import { EXERCISE_LABELS, ListeningHistoryItem } from '../lib/listening'

function formatDate(iso: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  } catch {
    return ''
  }
}

export default function ListeningHistoryPage() {
  const [items, setItems] = useState<ListeningHistoryItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ items: ListeningHistoryItem[] }>('/api/v1/listening/history')
      .then((r) => setItems(r.items))
      .catch((e) => setError((e as Error).message))
  }, [])

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-end">
        <Link
          to="/listening"
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          Bài mới
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-fg">Lịch sử luyện nghe</h1>
      </div>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
          {error}
        </div>
      )}

      {items === null && !error ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-surface rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items && items.length === 0 ? (
        <EmptyState
          illustration="empty-listening"
          title="Chưa có bài luyện nghe nào"
          description="Chọn một dạng bài ở Listening Gym để bắt đầu buổi luyện đầu tiên."
          primaryAction={{ label: 'Bắt đầu luyện', to: '/listening' }}
        />
      ) : (
        <div className="space-y-2">
          {items?.map((it) => {
            const label = EXERCISE_LABELS[it.exercise_type]
            return (
              <Link
                key={it.id}
                to={`/listening/${it.id}`}
                className="block bg-surface-raised rounded-xl border border-border hover:border-primary/40 p-3 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Icon name={label.icon} size="lg" variant="primary" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-fg truncate">{it.title}</p>
                    <p className="text-xs text-muted-fg">
                      {label.title} · Band {it.band} · {formatDate(it.created_at)}
                    </p>
                  </div>
                  <span
                    className={`text-sm font-semibold ${
                      it.submitted ? 'text-primary' : 'text-muted-fg'
                    }`}
                  >
                    {it.submitted
                      ? `${Math.round((it.score ?? 0) * 100)}%`
                      : 'Chưa nộp'}
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
