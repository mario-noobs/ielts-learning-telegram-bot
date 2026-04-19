import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon, { IconName } from './Icon'
import { apiFetch } from '../lib/api'

interface CoachingTip {
  id: string
  skill: 'vocabulary' | 'writing' | 'listening' | 'reading' | 'overall'
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

// Reskinned from per-skill distinct hues to a single surface-based card style.
// Skill differentiation is carried by the icon; per-skill colour encoding was
// low-signal and leaked outside tokens.
const SKILL_META: Record<CoachingTip['skill'], { icon: IconName; color: string }> = {
  vocabulary: { icon: 'BookOpen', color: 'bg-surface border-border' },
  writing: { icon: 'PenLine', color: 'bg-surface border-border' },
  listening: { icon: 'Headphones', color: 'bg-surface border-border' },
  reading: { icon: 'FileText', color: 'bg-surface border-border' },
  overall: { icon: 'Target', color: 'bg-primary/10 border-primary/20' },
}

export default function CoachingPanel() {
  const { t, i18n } = useTranslation('progress')
  const [data, setData] = useState<RecommendationsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<RecommendationsResponse>('/api/v1/progress/recommendations')
      .then(setData)
      .catch((e) => setError((e as Error).message))
  }, [])

  const isVi = i18n.language.startsWith('vi')

  if (error) {
    return (
      <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
        {t('recommendationsError', { error })}
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
          {t('recommendationsHeading')}
        </h2>
        <span className="text-xs text-muted-fg">{data.week_key}</span>
      </div>

      {data.tips.length === 0 ? (
        <p className="text-sm text-muted-fg">{t('recommendationsEmpty')}</p>
      ) : (
        <div className="space-y-2">
          {data.tips.map((tip) => {
            const meta = SKILL_META[tip.skill] ?? SKILL_META.overall
            // Render only the tip text for the active locale. Falls back to the
            // other locale if the server didn't supply one (rare).
            const body = isVi
              ? (tip.tip_vi || tip.tip_en)
              : (tip.tip_en || tip.tip_vi)
            const actionLabel = t(
              `recommendationsActionBySkill.${tip.skill}`,
              { defaultValue: tip.action_label },
            )
            return (
              <div
                key={tip.id}
                className={`rounded-xl border p-3 ${meta.color}`}
              >
                <div className="flex items-start gap-3">
                  <Icon name={meta.icon} size="lg" variant="primary" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-fg text-sm">{body}</p>
                  </div>
                  <Link
                    to={tip.action_route}
                    className="text-xs font-medium text-primary hover:text-primary-hover bg-surface-raised border border-primary/30 rounded-full px-3 py-1 shrink-0"
                  >
                    {actionLabel} →
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
