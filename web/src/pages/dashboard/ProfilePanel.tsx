import { useTranslation } from 'react-i18next'
import { Badge } from '../../components/ui'
import Icon, { IconName } from '../../components/Icon'
import type { ProgressResponse } from '../../lib/progress'
import { deltaFrom } from '../../lib/progress'

interface Profile {
  name: string
  email: string | null
  streak: number
  total_words: number
}

interface Props {
  profile: Profile
  progress: ProgressResponse | null
}

type StatRow = {
  label: string
  value: string
  trend: 'up' | 'down' | 'flat'
}

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function trendIcon(t: StatRow['trend']): IconName {
  if (t === 'up') return 'TrendingUp'
  if (t === 'down') return 'TrendingDown'
  return 'Minus'
}

function trendVariant(t: StatRow['trend']): 'success' | 'danger' | 'muted' {
  if (t === 'up') return 'success'
  if (t === 'down') return 'danger'
  return 'muted'
}

export default function ProfilePanel({ profile, progress }: Props) {
  const { t } = useTranslation('dashboard')
  const bandDelta = progress ? deltaFrom(progress.trend, 'overall_band') : 0
  const writingSamples = progress?.snapshot.skills.writing.sample_size ?? 0
  const listeningSessions = progress?.snapshot.skills.listening.sample_size ?? 0
  const readingSessions = progress?.snapshot.skills.reading?.sample_size ?? 0

  const stats: StatRow[] = [
    {
      label: t('profilePanel.stats.flashcards'),
      value: String(profile.total_words),
      trend: profile.total_words > 0 ? 'up' : 'flat',
    },
    {
      label: t('profilePanel.stats.writingSubmitted'),
      value: String(writingSamples),
      trend: writingSamples > 0 ? 'up' : 'flat',
    },
    {
      label: t('profilePanel.stats.listeningSessions'),
      value: String(listeningSessions),
      trend: listeningSessions > 0 ? 'up' : 'flat',
    },
    {
      label: t('profilePanel.stats.readingSessions'),
      value: String(readingSessions),
      trend: readingSessions > 0 ? 'up' : 'flat',
    },
    {
      label: t('profilePanel.stats.bandDelta30d'),
      value: `${bandDelta > 0 ? '+' : ''}${bandDelta.toFixed(1)}`,
      trend: bandDelta > 0 ? 'up' : bandDelta < 0 ? 'down' : 'flat',
    },
  ]

  return (
    <aside
      aria-labelledby="profile-panel-heading"
      className="flex flex-col gap-4 lg:sticky lg:top-4"
    >
      <h2 id="profile-panel-heading" className="sr-only">
        {t('profilePanel.statsHeading')}
      </h2>

      {/* Identity card */}
      <div className="rounded-2xl border border-border bg-surface-raised p-5">
        <div className="flex items-center gap-3">
          <div
            aria-hidden="true"
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-teal-100 text-lg font-semibold text-teal-800"
          >
            {initialsOf(profile.name)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-fg">{profile.name}</p>
            {profile.email && (
              <p className="truncate text-xs text-muted-fg">{profile.email}</p>
            )}
            <div className="mt-1">
              <Badge variant="primary">{t('profilePanel.beta')}</Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Streak card */}
      <div className="rounded-2xl border border-border bg-surface-raised p-5">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="text-2xl">
            🔥
          </span>
          <p className="text-sm font-semibold text-fg">
            {t('profilePanel.streakHeading')}
          </p>
        </div>
        <p className="mt-2 text-3xl font-bold text-fg">
          {t('profilePanel.streakDays', { count: profile.streak })}
        </p>
        {profile.streak === 0 && (
          <p className="mt-1 text-xs text-muted-fg">
            {t('profilePanel.streakEmpty')}
          </p>
        )}
      </div>

      {/* Stats card */}
      <div className="rounded-2xl border border-border bg-surface-raised p-5">
        <p className="text-sm font-semibold text-fg">
          {t('profilePanel.statsHeading')}
        </p>
        <ul className="mt-3 flex flex-col gap-2.5">
          {stats.map((s) => (
            <li
              key={s.label}
              className="flex items-center justify-between gap-3"
            >
              <span className="text-sm text-muted-fg">{s.label}</span>
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-fg">
                <Icon
                  name={trendIcon(s.trend)}
                  size="sm"
                  variant={trendVariant(s.trend)}
                />
                {s.value}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}
