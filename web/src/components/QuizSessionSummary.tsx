import { Link } from 'react-router-dom'
import { formatNextReview, type AnswerRecord } from '../lib/quizTypes'

interface Props {
  records: AnswerRecord[]
  onRestart: () => void
  backTo?: string
  t: (k: string, o?: Record<string, unknown>) => string
}

export default function QuizSessionSummary({
  records,
  onRestart,
  backTo = '/vocab',
  t,
}: Props) {
  const correct = records.filter((r) => r.result.is_correct).length
  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="bg-surface-raised rounded-xl shadow-sm p-6 text-center">
        <h2 className="text-sm uppercase tracking-wide text-muted-fg mb-2">
          {t('review.resultsHeading')}
        </h2>
        <div className="text-5xl font-bold text-primary">
          {correct}
          <span className="text-2xl text-muted-fg">/{records.length}</span>
        </div>
      </div>
      <div className="space-y-2">
        {records.map((r, i) => (
          <div
            key={i}
            className="bg-surface-raised rounded-lg p-3 flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-3">
              <span
                className={
                  r.result.is_correct
                    ? 'text-success font-bold'
                    : 'text-danger font-bold'
                }
              >
                {r.result.is_correct ? '✓' : '✗'}
              </span>
              <span className="text-fg truncate max-w-[180px]">
                {r.question.question}
              </span>
            </div>
            <div className="text-xs text-muted-fg">
              {r.result.srs_update.old_strength} → {r.result.srs_update.new_strength} ·{' '}
              {formatNextReview(r.result.srs_update.next_review, t)}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-3">
        <button
          onClick={onRestart}
          className="flex-1 py-3 bg-primary text-primary-fg rounded-xl font-medium hover:bg-primary-hover"
        >
          {t('review.reviewAgainBtn')}
        </button>
        <Link
          to={backTo}
          className="flex-1 py-3 bg-surface text-fg rounded-xl font-medium hover:bg-border text-center"
        >
          {t('review.backToVocabBtn')}
        </Link>
      </div>
    </div>
  )
}
