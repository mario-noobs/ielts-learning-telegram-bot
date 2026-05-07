import { useEffect, useRef } from 'react'
import Icon from './Icon'
import type { QuizAnswerResponse } from '../lib/quizTypes'

interface Props {
  result: QuizAnswerResponse
  onContinue: () => void
  isLast: boolean
  t: (k: string) => string
}

export default function QuizFeedbackOverlay({ result, onContinue, isLast, t }: Props) {
  const continueRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    continueRef.current?.focus()
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault()
        onContinue()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onContinue])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-title"
      className="fixed inset-0 bg-scrim flex items-center justify-center z-50 p-4"
    >
      <div className="bg-surface-raised dark:bg-surface rounded-2xl p-6 max-w-md w-full shadow-xl">
        <div className="flex items-center gap-3 mb-3">
          <Icon
            name={result.is_correct ? 'CheckCircle2' : 'AlertCircle'}
            size="xl"
            variant={result.is_correct ? 'success' : 'danger'}
            label={result.is_correct ? t('review.correct') : t('review.incorrect')}
          />
          <h2
            id="feedback-title"
            className={`text-2xl font-bold ${result.is_correct ? 'text-success' : 'text-danger'}`}
          >
            {result.is_correct ? t('review.correctTitle') : t('review.incorrectTitle')}
          </h2>
        </div>
        <p className="text-fg whitespace-pre-line">{result.feedback}</p>
        {result.srs_update.strength_change && (
          <p className="mt-3 text-xs text-muted-fg tabular-nums">
            {result.srs_update.old_strength} → {result.srs_update.new_strength}
          </p>
        )}
        <button
          ref={continueRef}
          onClick={onContinue}
          className="mt-5 w-full py-3 min-h-[44px] bg-primary text-primary-fg rounded-xl font-medium hover:bg-primary-hover"
        >
          {isLast ? t('review.seeResultsBtn') : t('review.continueBtn')} {t('review.continueHint')}
        </button>
      </div>
    </div>
  )
}
