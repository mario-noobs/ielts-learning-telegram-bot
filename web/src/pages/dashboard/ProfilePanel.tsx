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
  const bandDelta = progress ? deltaFrom(progress.trend, 'overall_band') : 0
  const writingSamples = progress?.snapshot.skills.writing.sample_size ?? 0
  const listeningSessions = progress?.snapshot.skills.listening.sample_size ?? 0
  const readingSessions = progress?.snapshot.skills.reading?.sample_size ?? 0

  const stats: StatRow[] = [
    {
      label: 'Flashcard đã học',
      value: String(profile.total_words),
      trend: profile.total_words > 0 ? 'up' : 'flat',
    },
    {
      label: 'Bài Writing đã nộp',
      value: String(writingSamples),
      trend: writingSamples > 0 ? 'up' : 'flat',
    },
    {
      label: 'Buổi Listening',
      value: String(listeningSessions),
      trend: listeningSessions > 0 ? 'up' : 'flat',
    },
    {
      label: 'Bài Reading',
      value: String(readingSessions),
      trend: readingSessions > 0 ? 'up' : 'flat',
    },
    {
      label: 'Đổi band 30 ngày',
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
        Thông tin của bạn
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
              <Badge variant="primary">Beta</Badge>
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
          <p className="text-sm font-semibold text-fg">Chuỗi ngày luyện</p>
        </div>
        <p className="mt-2 text-3xl font-bold text-fg">
          {profile.streak}{' '}
          <span className="text-sm font-medium text-muted-fg">
            {profile.streak === 1 ? 'ngày' : 'ngày'}
          </span>
        </p>
        {profile.streak === 0 && (
          <p className="mt-1 text-xs text-muted-fg">
            Hoàn thành một bài hôm nay để bắt đầu chuỗi.
          </p>
        )}
      </div>

      {/* Stats card */}
      <div className="rounded-2xl border border-border bg-surface-raised p-5">
        <p className="text-sm font-semibold text-fg">Thống kê</p>
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
