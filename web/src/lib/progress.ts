export interface VocabSkill {
  band: number
  total_words: number
  mastered_count: number
}

export interface WritingSkill {
  band: number
  sample_size: number
}

export interface ListeningSkill {
  band: number
  sample_size: number
  accuracy_by_type: Record<string, number>
}

export interface SkillBreakdown {
  vocabulary: VocabSkill
  writing: WritingSkill
  listening: ListeningSkill
}

export interface ProgressSnapshot {
  overall_band: number
  skills: SkillBreakdown
  target_band: number
  date: string | null
  generated_at: string | null
}

export interface TrendPoint {
  date: string
  overall_band: number
  vocabulary_band: number
  writing_band: number
  listening_band: number
}

export interface ProgressPrediction {
  days_ahead: number
  projected_band: number
}

export interface ProgressResponse {
  snapshot: ProgressSnapshot
  trend: TrendPoint[]
  predictions: ProgressPrediction[]
}

export function deltaFrom(
  trend: TrendPoint[],
  key: keyof TrendPoint,
): number {
  if (trend.length < 2) return 0
  const firstNonZero = trend.find(
    (p) => typeof p[key] === 'number' && (p[key] as number) > 0,
  )
  const last = trend[trend.length - 1]
  if (!firstNonZero || !last) return 0
  const start = Number(firstNonZero[key]) || 0
  const end = Number(last[key]) || 0
  return Math.round((end - start) * 10) / 10
}

export function timeToTarget(
  current: number,
  target: number,
  trend: TrendPoint[],
): string | null {
  if (current >= target) return 'Đã đạt mục tiêu'
  if (trend.length < 3) return null
  const first = trend.find((p) => p.overall_band > 0)
  const last = trend[trend.length - 1]
  if (!first || !last) return null
  const daysSpan = trend.indexOf(last) - trend.indexOf(first)
  if (daysSpan <= 0) return null
  const rate = (last.overall_band - first.overall_band) / daysSpan
  if (rate <= 0) return 'Cần tăng nhịp luyện tập'
  const remaining = (target - current) / rate
  return `Dự kiến ${Math.round(remaining)} ngày nữa`
}
