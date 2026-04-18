import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'

interface CoachingTip {
  id: string
  skill: 'vocabulary' | 'writing' | 'listening' | 'overall'
  tip_en: string
  tip_vi: string
  action_label: string
  action_route: string
}

interface RecommendationsResponse {
  week_key: string
  tips: CoachingTip[]
  generated_at: string | null
}

const SKILL_META: Record<CoachingTip['skill'], { emoji: string; color: string }> = {
  vocabulary: { emoji: '📚', color: 'bg-amber-50 border-amber-200' },
  writing: { emoji: '✍️', color: 'bg-emerald-50 border-emerald-200' },
  listening: { emoji: '🎧', color: 'bg-fuchsia-50 border-fuchsia-200' },
  overall: { emoji: '🎯', color: 'bg-indigo-50 border-indigo-200' },
}

export default function CoachingPanel() {
  const [data, setData] = useState<RecommendationsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<RecommendationsResponse>('/api/v1/progress/recommendations')
      .then(setData)
      .catch((e) => setError((e as Error).message))
  }, [])

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-sm text-red-700">
        Không tải được gợi ý: {error}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="space-y-2">
        <div className="h-4 w-32 bg-gray-100 rounded animate-pulse" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">
          Gợi ý của coach tuần này
        </h2>
        <span className="text-xs text-gray-400">{data.week_key}</span>
      </div>

      {data.tips.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có gợi ý cho tuần này.</p>
      ) : (
        <div className="space-y-2">
          {data.tips.map((tip) => {
            const meta = SKILL_META[tip.skill] ?? SKILL_META.overall
            return (
              <div
                key={tip.id}
                className={`rounded-xl border p-3 ${meta.color}`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-xl">{meta.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 text-sm">
                      {tip.tip_vi}
                    </p>
                    {tip.tip_en && (
                      <p className="text-xs text-gray-600 mt-0.5">
                        {tip.tip_en}
                      </p>
                    )}
                  </div>
                  <Link
                    to={tip.action_route}
                    className="text-xs font-medium text-indigo-700 hover:text-indigo-900 bg-white border border-indigo-200 rounded-full px-3 py-1 shrink-0"
                  >
                    {tip.action_label} →
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
