export type ActivityType =
  | 'srs_review'
  | 'daily_words'
  | 'listening'
  | 'reading'
  | 'writing'
  | 'quiz'

export interface PlanActivity {
  id: string
  type: ActivityType
  title: string
  description: string
  estimated_minutes: number
  route: string
  meta: Record<string, string>
  completed: boolean
}

export interface DailyPlan {
  date: string
  activities: PlanActivity[]
  total_minutes: number
  cap_minutes: number
  exam_urgent: boolean
  days_until_exam: number | null
  completed_count: number
  generated_at: string | null
}

import type { IconName } from '../components/Icon'

export const TYPE_META: Record<
  ActivityType,
  { icon: IconName; color: string }
> = {
  srs_review: { icon: 'RotateCcw', color: 'from-amber-400 to-orange-500' },
  daily_words: { icon: 'BookOpen', color: 'from-sky-400 to-indigo-500' },
  listening: { icon: 'Headphones', color: 'from-fuchsia-400 to-purple-500' },
  reading: { icon: 'FileText', color: 'from-cyan-400 to-sky-500' },
  writing: { icon: 'PenLine', color: 'from-emerald-400 to-teal-500' },
  quiz: { icon: 'Zap', color: 'from-rose-400 to-pink-500' },
}

/**
 * Translate a plan activity's display copy using its type + meta. The
 * backend still returns VN title/description for bot compatibility
 * (Telegram stays VN-first); the web frontend derives its own copy from
 * activity.type so EN-default users never see untranslated strings.
 */
export function activityDisplay(
  activity: PlanActivity,
  t: (key: string, opts?: Record<string, unknown>) => string,
): { title: string; description: string } {
  const meta = activity.meta ?? {}
  switch (activity.type) {
    case 'srs_review':
      return {
        title: t('plan:activity.srs_review.title'),
        description: activity.description, // backend carries the due count
      }
    case 'daily_words':
      return {
        title: t('plan:activity.daily_words.title'),
        description: t('plan:activity.daily_words.description'),
      }
    case 'listening': {
      const sub = (meta.exercise_type as string) || 'dictation'
      return {
        title: t(`plan:activity.listening.title.${sub}`),
        description: t('plan:activity.listening.description'),
      }
    }
    case 'reading':
      return {
        title: t('plan:activity.reading.title'),
        description: t('plan:activity.reading.description', {
          band: meta.band ?? '—',
          title: meta.title ?? '',
        }),
      }
    case 'writing': {
      const task = (meta.task_type as string) || 'task2'
      return {
        title: t(`plan:activity.writing.title.${task}`),
        description: t('plan:activity.writing.description'),
      }
    }
    case 'quiz':
      return {
        title: t('plan:activity.sprint_quiz.title'),
        description: t('plan:activity.sprint_quiz.description'),
      }
    default:
      return { title: activity.title, description: activity.description }
  }
}

export type TimeOfDay = 'morning' | 'afternoon' | 'evening'

export function timeOfDay(date: Date): TimeOfDay {
  const h = date.getHours()
  if (h < 12) return 'morning'
  if (h < 18) return 'afternoon'
  return 'evening'
}
