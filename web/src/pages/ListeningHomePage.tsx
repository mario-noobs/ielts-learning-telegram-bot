import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import {
  EXERCISE_LABELS,
  ListeningExerciseView,
  ListeningType,
} from '../lib/listening'

const TYPES: ListeningType[] = ['dictation', 'gap_fill', 'comprehension']

export default function ListeningHomePage() {
  const navigate = useNavigate()
  const [starting, setStarting] = useState<ListeningType | null>(null)
  const [error, setError] = useState<string | null>(null)

  const start = async (exercise_type: ListeningType) => {
    if (starting) return
    setStarting(exercise_type)
    setError(null)
    try {
      const res = await apiFetch<ListeningExerciseView>(
        '/api/v1/listening/generate',
        {
          method: 'POST',
          body: JSON.stringify({ exercise_type }),
        },
      )
      navigate(`/listening/${res.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setStarting(null)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">
          ← Trang chủ
        </Link>
        <Link
          to="/listening/history"
          className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
        >
          Lịch sử
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Listening Gym</h1>
        <p className="text-sm text-gray-500 mt-1">
          Luyện nghe ở band mục tiêu của bạn.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {TYPES.map((t) => {
          const label = EXERCISE_LABELS[t]
          const disabled = !!starting
          return (
            <button
              key={t}
              onClick={() => start(t)}
              disabled={disabled}
              className="w-full text-left bg-white rounded-xl border border-gray-200 hover:border-indigo-300 hover:shadow-sm p-4 flex items-center gap-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="text-3xl">{label.emoji}</span>
              <div className="flex-1">
                <p className="font-semibold text-gray-900">{label.title}</p>
                <p className="text-sm text-gray-500">{label.description}</p>
              </div>
              <span className="text-sm text-indigo-600">
                {starting === t ? 'Đang tạo...' : 'Bắt đầu →'}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
