import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import { apiFetch } from '../lib/api'
import {
  EXERCISE_LABELS,
  ListeningExerciseView,
  ListeningHistoryItem,
  ListeningType,
} from '../lib/listening'

const TYPES: ListeningType[] = ['dictation', 'gap_fill', 'comprehension']
const TIME_ESTIMATES: Record<ListeningType, string> = {
  dictation: '2–3 phút',
  gap_fill: '3–4 phút',
  comprehension: '4–5 phút',
}

interface UserProfile {
  target_band: number
}

export default function ListeningHomePage() {
  const navigate = useNavigate()
  const [starting, setStarting] = useState<ListeningType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [band, setBand] = useState<number>(7.0)
  const [recent, setRecent] = useState<ListeningHistoryItem[]>([])

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setBand(p.target_band))
      .catch(() => {})
    apiFetch<{ items: ListeningHistoryItem[] }>('/api/v1/listening/history')
      .then((r) => setRecent(r.items.slice(0, 3)))
      .catch(() => {})
  }, [])

  const start = async (exercise_type: ListeningType) => {
    if (starting) return
    setStarting(exercise_type)
    setError(null)
    try {
      const res = await apiFetch<ListeningExerciseView>(
        '/api/v1/listening/generate',
        { method: 'POST', body: JSON.stringify({ exercise_type }) },
      )
      navigate(`/listening/${res.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setStarting(null)
    }
  }

  const submittedToday = recent.filter(
    (r) => r.submitted && r.created_at &&
      new Date(r.created_at).toDateString() === new Date().toDateString(),
  ).length

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-end">
        <Link
          to="/listening/history"
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          Lịch sử
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-fg">Listening Gym</h1>
        <p className="text-sm text-muted-fg mt-1">
          Luyện nghe ở Band {band}. Hôm nay đã hoàn thành {submittedToday} bài.
        </p>
      </div>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {TYPES.map((t) => {
          const label = EXERCISE_LABELS[t]
          return (
            <button
              key={t}
              onClick={() => start(t)}
              disabled={!!starting}
              className="w-full text-left bg-surface-raised rounded-xl border border-border hover:border-primary/40 hover:shadow-sm p-4 flex items-center gap-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Icon name={label.icon} size="xl" variant="primary" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-fg">{label.title}</p>
                  <span className="text-[10px] font-semibold text-primary bg-primary/10 border border-primary/20 rounded-full px-2 py-0.5">
                    Band {band}
                  </span>
                </div>
                <p className="text-sm text-muted-fg">{label.description}</p>
                <p className="text-xs text-muted-fg mt-0.5 inline-flex items-center gap-1">
                  <Icon name="Clock" size="sm" variant="muted" /> {TIME_ESTIMATES[t]}
                </p>
              </div>
              <span className="text-sm text-primary">
                {starting === t ? 'Đang tạo...' : 'Bắt đầu →'}
              </span>
            </button>
          )
        })}
      </div>

      {recent.length > 0 && (
        <div className="pt-4">
          <h2 className="text-sm font-semibold text-fg mb-2">Gần đây</h2>
          <div className="space-y-2">
            {recent.map((it) => {
              const label = EXERCISE_LABELS[it.exercise_type]
              return (
                <Link
                  key={it.id}
                  to={`/listening/${it.id}`}
                  className="flex items-center gap-3 bg-surface-raised rounded-lg border border-border hover:border-primary/40 p-2.5 text-sm"
                >
                  <Icon name={label.icon} size="md" variant="primary" />
                  <span className="flex-1 text-fg truncate">{it.title}</span>
                  <span
                    className={`text-xs font-semibold ${
                      it.submitted ? 'text-primary' : 'text-muted-fg'
                    }`}
                  >
                    {it.submitted ? `${Math.round((it.score ?? 0) * 100)}%` : '—'}
                  </span>
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
