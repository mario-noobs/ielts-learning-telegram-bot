export interface QuizQuestion {
  id: string
  type: string
  question: string
  options: string[]
  word_id: string
}

export interface QuizStartResponse {
  session_id: string
  questions: QuizQuestion[]
}

export interface SRSUpdate {
  next_review: string | null
  old_strength: string
  new_strength: string
  strength_change: boolean
}

export interface QuizAnswerResponse {
  is_correct: boolean
  feedback: string
  srs_update: SRSUpdate
}

export interface AnswerRecord {
  question: QuizQuestion
  answer: string
  result: QuizAnswerResponse
}

export function formatNextReview(
  iso: string | null,
  t: (k: string, o?: Record<string, unknown>) => string,
): string {
  if (!iso) return '—'
  const diffMs = new Date(iso).getTime() - Date.now()
  const diffMin = Math.round(diffMs / 60000)
  if (diffMin <= 0) return t('review.nextReviewIn.now')
  if (diffMin < 60) return t('review.nextReviewIn.inMinutes', { count: diffMin })
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return t('review.nextReviewIn.inHours', { count: diffHr })
  const diffDay = Math.round(diffHr / 24)
  return t('review.nextReviewIn.inDays', { count: diffDay })
}
