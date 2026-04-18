export type ActivityType =
  | 'srs_review'
  | 'daily_words'
  | 'listening'
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

export const TYPE_META: Record<
  ActivityType,
  { emoji: string; color: string }
> = {
  srs_review: { emoji: '🔁', color: 'from-amber-400 to-orange-500' },
  daily_words: { emoji: '📖', color: 'from-sky-400 to-indigo-500' },
  listening: { emoji: '🎧', color: 'from-fuchsia-400 to-purple-500' },
  writing: { emoji: '✍️', color: 'from-emerald-400 to-teal-500' },
  quiz: { emoji: '⚡', color: 'from-rose-400 to-pink-500' },
}

export function greetingFor(date: Date): string {
  const h = date.getHours()
  if (h < 12) return 'Chào buổi sáng'
  if (h < 18) return 'Chào buổi chiều'
  return 'Chào buổi tối'
}
