import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Icon, { IconName } from './Icon'
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

// Note: reskinned from per-skill distinct hues (amber/emerald/fuchsia/indigo) to a
// single surface-based card style. Skill differentiation is carried by the icon
// and label; per-skill colour encoding was low-signal and leaked outside tokens.
const SKILL_META: Record<CoachingTip['skill'], { icon: IconName; color: string }> = {
  vocabulary: { icon: 'BookOpen', color: 'bg-surface border-border' },
  writing: { icon: 'PenLine', color: 'bg-surface border-border' },
  listening: { icon: 'Headphones', color: 'bg-surface border-border' },
  overall: { icon: 'Target', color: 'bg-primary/10 border-primary/20' },
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
      <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
        Không tải được gợi ý: {error}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="space-y-2">
        <div className="h-4 w-32 bg-surface rounded animate-pulse" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 bg-surface rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-fg">
          Gợi ý của coach tuần này
        </h2>
        <span className="text-xs text-muted-fg">{data.week_key}</span>
      </div>

      {data.tips.length === 0 ? (
        <p className="text-sm text-muted-fg">Chưa có gợi ý cho tuần này.</p>
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
                  <Icon name={meta.icon} size="lg" variant="primary" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-fg text-sm">
                      {tip.tip_vi}
                    </p>
                    {tip.tip_en && (
                      <p className="text-xs text-muted-fg mt-0.5">
                        {tip.tip_en}
                      </p>
                    )}
                  </div>
                  <Link
                    to={tip.action_route}
                    className="text-xs font-medium text-primary hover:text-primary-hover bg-surface-raised border border-primary/30 rounded-full px-3 py-1 shrink-0"
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
