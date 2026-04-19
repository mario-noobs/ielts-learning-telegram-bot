import { Link } from 'react-router-dom'
import SkillBandCard from '../../components/SkillBandCard'
import type { ProgressResponse } from '../../lib/progress'
import { deltaFrom } from '../../lib/progress'
import { track } from '../../lib/analytics'

interface Props {
  progress: ProgressResponse | null
}

type SkillKey = 'writing' | 'listening' | 'vocabulary' | 'reading'

const SKILLS: Array<{
  key: SkillKey
  label: string
  iconName: 'PenLine' | 'Headphones' | 'BookOpen' | 'FileText'
  to: string
}> = [
  { key: 'writing', label: 'Writing', iconName: 'PenLine', to: '/write' },
  { key: 'listening', label: 'Listening', iconName: 'Headphones', to: '/listening' },
  { key: 'vocabulary', label: 'Vocab', iconName: 'BookOpen', to: '/vocab' },
  { key: 'reading', label: 'Reading', iconName: 'FileText', to: '/reading' },
]

export default function ReadinessStrip({ progress }: Props) {
  const target = progress?.snapshot.target_band ?? 7.0

  return (
    <section aria-labelledby="readiness-heading">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="readiness-heading" className="font-semibold text-fg">
          Mức độ sẵn sàng
        </h2>
        <Link
          to="/progress"
          className="text-sm text-primary hover:text-primary-hover focus-visible:outline-none focus-visible:underline"
        >
          Xem chi tiết →
        </Link>
      </div>

      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:grid md:grid-cols-4 md:gap-3 md:overflow-visible md:px-0 md:pb-0">
        {SKILLS.map((s) => {
          const card = progress
            ? {
                band: progress.snapshot.skills[s.key].band,
                target,
                delta: deltaFrom(
                  progress.trend,
                  `${s.key}_band` as
                    | 'writing_band'
                    | 'listening_band'
                    | 'vocabulary_band'
                    | 'reading_band',
                ),
                subline: undefined,
              }
            : { band: 0, target, delta: 0, subline: 'Đang tải…' }

          return (
            <Link
              key={s.key}
              to={s.to}
              onClick={() =>
                track('dashboard_readiness_card_click', { skill: s.key })
              }
              className="min-w-[220px] snap-start rounded-xl md:min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <SkillBandCard
                iconName={s.iconName}
                label={s.label}
                band={card.band}
                target={card.target}
                delta={card.delta}
                subline={card.subline}
              />
            </Link>
          )
        })}
      </div>
    </section>
  )
}
