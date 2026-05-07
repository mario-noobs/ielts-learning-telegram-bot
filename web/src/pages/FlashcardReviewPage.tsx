import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import MultipleChoiceQuestion from '../components/MultipleChoiceQuestion'
import QuizFeedbackOverlay from '../components/QuizFeedbackOverlay'
import QuizSessionSummary from '../components/QuizSessionSummary'
import { apiFetch } from '../lib/api'
import type {
  AnswerRecord,
  QuizAnswerResponse,
  QuizQuestion,
  QuizStartResponse,
} from '../lib/quizTypes'

type Mode = 'mcq' | 'flip'
type Phase =
  | 'pre'
  | 'mcq-question'
  | 'mcq-feedback'
  | 'mcq-summary'
  | 'flip-front'
  | 'flip-back'
  | 'flip-summary'

type Rating = 'again' | 'good' | 'easy'

interface DueWord {
  word_id: string
  word: string
  ipa: string
  part_of_speech: string
  definition_en: string
  definition_vi: string
  example_en: string
  example_vi: string
  strength: string
}

interface DueResponse {
  items: DueWord[]
}

interface RateResponse {
  word_id: string
  old_strength: string
  new_strength: string
  strength_change: boolean
  next_review: string | null
}

interface FlipRecord {
  word: DueWord
  rating: Rating
  result: RateResponse
}

function ProgressBar({
  current,
  total,
  t,
}: {
  current: number
  total: number
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const pct = total > 0 ? (current / total) * 100 : 0
  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-muted-fg mb-1 tabular-nums">
        <span>
          {current} / {total}
        </span>
      </div>
      <div
        className="h-2 bg-border rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={t('review.progressAria', { current, total })}
      >
        <div
          className="h-full bg-primary transition-[width] duration-slow ease-out-soft"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function FlashcardReviewPage() {
  const { t } = useTranslation('vocab')
  const [mode, setMode] = useState<Mode | null>(null)
  const [phase, setPhase] = useState<Phase>('pre')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // MCQ state
  const [sessionId, setSessionId] = useState<string>('')
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [records, setRecords] = useState<AnswerRecord[]>([])
  const [feedback, setFeedback] = useState<QuizAnswerResponse | null>(null)

  // Flip-card state
  const [flipWords, setFlipWords] = useState<DueWord[]>([])
  const [flipIndex, setFlipIndex] = useState(0)
  const [flipRecords, setFlipRecords] = useState<FlipRecord[]>([])

  const startMcq = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<QuizStartResponse>('/api/v1/quiz/start', {
        method: 'POST',
        body: JSON.stringify({ count: 10, types: ['multiple_choice'] }),
      })
      const supported = res.questions.filter((q) => q.type === 'multiple_choice')
      if (supported.length === 0) {
        setError(t('review.noQuestions'))
        setLoading(false)
        return
      }
      setSessionId(res.session_id)
      setQuestions(supported)
      setIndex(0)
      setRecords([])
      setMode('mcq')
      setPhase('mcq-question')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [t])

  const startFlip = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<DueResponse>('/api/v1/review/due', {
        method: 'POST',
        body: JSON.stringify({ limit: 10 }),
      })
      if (res.items.length === 0) {
        setError(t('review.noDueWords.description'))
        setLoading(false)
        return
      }
      setFlipWords(res.items)
      setFlipIndex(0)
      setFlipRecords([])
      setMode('flip')
      setPhase('flip-front')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [t])

  const restart = useCallback(() => {
    setMode(null)
    setPhase('pre')
    setError(null)
    setQuestions([])
    setRecords([])
    setFeedback(null)
    setFlipWords([])
    setFlipRecords([])
  }, [])

  // ─── MCQ flow ────────────────────────────────────────────────────────
  const submitMcq = useCallback(
    async (answer: string) => {
      const q = questions[index]
      if (!q) return
      try {
        const res = await apiFetch<QuizAnswerResponse>('/api/v1/quiz/answer', {
          method: 'POST',
          body: JSON.stringify({
            session_id: sessionId,
            question_id: q.id,
            answer,
          }),
        })
        setRecords((rs) => [...rs, { question: q, answer, result: res }])
        setFeedback(res)
        setPhase('mcq-feedback')
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [questions, index, sessionId],
  )

  const advanceMcq = useCallback(() => {
    if (index + 1 >= questions.length) {
      setPhase('mcq-summary')
    } else {
      setIndex((i) => i + 1)
      setPhase('mcq-question')
    }
    setFeedback(null)
  }, [index, questions.length])

  // ─── Flip-card flow ──────────────────────────────────────────────────
  const reveal = useCallback(() => setPhase('flip-back'), [])

  const rateFlip = useCallback(
    async (rating: Rating) => {
      const word = flipWords[flipIndex]
      if (!word) return
      try {
        const res = await apiFetch<RateResponse>('/api/v1/review/rate', {
          method: 'POST',
          body: JSON.stringify({ word_id: word.word_id, rating }),
        })
        setFlipRecords((rs) => [...rs, { word, rating, result: res }])
        if (flipIndex + 1 >= flipWords.length) {
          setPhase('flip-summary')
        } else {
          setFlipIndex((i) => i + 1)
          setPhase('flip-front')
        }
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [flipWords, flipIndex],
  )

  // Space to reveal on flip-front
  useEffect(() => {
    if (phase !== 'flip-front') return
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault()
        reveal()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [phase, reveal])

  // 1/2/3 to rate on flip-back
  useEffect(() => {
    if (phase !== 'flip-back') return
    const handler = (e: KeyboardEvent) => {
      if (e.key === '1') rateFlip('again')
      else if (e.key === '2') rateFlip('good')
      else if (e.key === '3') rateFlip('easy')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [phase, rateFlip])

  const currentQuestion = useMemo(() => questions[index], [questions, index])
  const currentWord = useMemo(() => flipWords[flipIndex], [flipWords, flipIndex])

  // ─── Render ──────────────────────────────────────────────────────────

  if (phase === 'pre') {
    if (error && error.toLowerCase().includes('enough')) {
      return (
        <div className="max-w-lg mx-auto p-4">
          <EmptyState
            illustration="empty-vocab"
            title={t('review.noDueWords.title')}
            description={t('review.noDueWords.description')}
            primaryAction={{ label: t('review.noDueWords.cta'), to: '/vocab' }}
          />
        </div>
      )
    }
    return (
      <div className="max-w-lg mx-auto p-4">
        <div className="bg-surface-raised rounded-xl shadow-sm p-6">
          <h1 className="text-2xl font-bold mb-2 text-fg">{t('review.heading')}</h1>
          <p className="text-muted-fg mb-6">{t('review.intro')}</p>
          {error && (
            <div className="bg-danger/10 border-l-4 border-danger p-3 rounded mb-4 text-danger text-sm">
              {error}
            </div>
          )}
          <p className="text-sm font-medium text-fg mb-3">
            {t('review.modePicker.heading')}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              onClick={startFlip}
              disabled={loading}
              className="p-4 min-h-[88px] rounded-xl border-2 border-border bg-surface text-left hover:border-primary hover:bg-primary/5 disabled:opacity-50 transition-colors"
            >
              <div className="text-lg mb-1">📖 {t('review.modePicker.flip')}</div>
              <div className="text-xs text-muted-fg">
                {t('review.modePicker.flipDesc')}
              </div>
            </button>
            <button
              onClick={startMcq}
              disabled={loading}
              className="p-4 min-h-[88px] rounded-xl border-2 border-border bg-surface text-left hover:border-primary hover:bg-primary/5 disabled:opacity-50 transition-colors"
            >
              <div className="text-lg mb-1">🎯 {t('review.modePicker.mcq')}</div>
              <div className="text-xs text-muted-fg">
                {t('review.modePicker.mcqDesc')}
              </div>
            </button>
          </div>
          {loading && (
            <p className="text-sm text-muted-fg mt-4 text-center">
              {t('review.startingBtn')}
            </p>
          )}
        </div>
      </div>
    )
  }

  // ─── MCQ render ──────────────────────────────────────────────────────
  if (mode === 'mcq') {
    if (phase === 'mcq-summary') {
      return <QuizSessionSummary records={records} onRestart={restart} t={t} />
    }

    if (!currentQuestion) return null

    return (
      <div className="max-w-2xl mx-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <button
            onClick={restart}
            className="text-sm text-muted-fg hover:text-fg"
          >
            {t('review.exit')}
          </button>
        </div>
        <ProgressBar current={index + 1} total={questions.length} t={t} />
        <div className="bg-surface-raised rounded-xl shadow-sm p-6">
          <p className="text-xl text-fg mb-6 whitespace-pre-line">
            {currentQuestion.question}
          </p>
          <MultipleChoiceQuestion
            options={currentQuestion.options}
            onSubmit={submitMcq}
            disabled={phase === 'mcq-feedback'}
            mcqOptionAria={(o) => t('review.mcqOptionAria', o)}
            keyboardHint={(keys) => t('review.keyboardHint', { keys })}
          />
        </div>
        {phase === 'mcq-feedback' && feedback && (
          <QuizFeedbackOverlay
            result={feedback}
            onContinue={advanceMcq}
            isLast={index + 1 >= questions.length}
            t={t}
          />
        )}
      </div>
    )
  }

  // ─── Flip-card render ────────────────────────────────────────────────
  if (mode === 'flip') {
    if (phase === 'flip-summary') {
      const correct = flipRecords.filter((r) => r.rating !== 'again').length
      return (
        <div className="max-w-2xl mx-auto p-4 space-y-4">
          <div className="bg-surface-raised rounded-xl shadow-sm p-6 text-center">
            <h2 className="text-sm uppercase tracking-wide text-muted-fg mb-2">
              {t('review.resultsHeading')}
            </h2>
            <div className="text-5xl font-bold text-primary">
              {correct}
              <span className="text-2xl text-muted-fg">/{flipRecords.length}</span>
            </div>
          </div>
          <div className="space-y-2">
            {flipRecords.map((r, i) => (
              <div
                key={i}
                className="bg-surface-raised rounded-lg p-3 flex items-center justify-between text-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl" aria-hidden>
                    {r.rating === 'again' ? '😕' : r.rating === 'good' ? '🙂' : '😎'}
                  </span>
                  <span className="text-fg font-medium">{r.word.word}</span>
                </div>
                <div className="text-xs text-muted-fg">
                  {r.result.old_strength} → {r.result.new_strength}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button
              onClick={restart}
              className="flex-1 py-3 bg-primary text-primary-fg rounded-xl font-medium hover:bg-primary-hover"
            >
              {t('review.reviewAgainBtn')}
            </button>
            <Link
              to="/vocab"
              className="flex-1 py-3 bg-surface text-fg rounded-xl font-medium hover:bg-border text-center"
            >
              {t('review.backToVocabBtn')}
            </Link>
          </div>
        </div>
      )
    }

    if (!currentWord) return null

    return (
      <div className="max-w-2xl mx-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <button
            onClick={restart}
            className="text-sm text-muted-fg hover:text-fg"
          >
            {t('review.exit')}
          </button>
        </div>
        <ProgressBar current={flipIndex + 1} total={flipWords.length} t={t} />
        <div className="bg-surface-raised rounded-xl shadow-sm p-6 text-center space-y-4">
          <div className="space-y-1">
            <h2 className="text-4xl font-bold text-fg">{currentWord.word}</h2>
            {currentWord.ipa && (
              <p className="text-sm text-muted-fg">{currentWord.ipa}</p>
            )}
            {currentWord.part_of_speech && (
              <p className="text-xs uppercase tracking-wide text-muted-fg">
                {currentWord.part_of_speech}
              </p>
            )}
          </div>

          {phase === 'flip-front' ? (
            <button
              onClick={reveal}
              className="w-full py-3 min-h-[44px] bg-primary text-primary-fg rounded-xl font-medium hover:bg-primary-hover"
            >
              👁️ {t('review.flip.reveal')} <span className="text-xs opacity-75">(Space)</span>
            </button>
          ) : (
            <>
              <div className="text-left space-y-2 border-t border-border pt-4">
                {currentWord.definition_en && (
                  <p className="text-fg">{currentWord.definition_en}</p>
                )}
                {currentWord.definition_vi && (
                  <p className="text-muted-fg text-sm">{currentWord.definition_vi}</p>
                )}
                {currentWord.example_en && (
                  <p className="text-sm text-fg italic pt-2">
                    "{currentWord.example_en}"
                  </p>
                )}
                {currentWord.example_vi && (
                  <p className="text-xs text-muted-fg italic">
                    "{currentWord.example_vi}"
                  </p>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 pt-2">
                <button
                  onClick={() => rateFlip('again')}
                  className="py-3 min-h-[44px] rounded-xl border-2 border-danger bg-danger/5 text-danger font-medium hover:bg-danger/10 transition-colors"
                >
                  😕 {t('review.flip.again')}
                  <div className="text-xs opacity-75">(1)</div>
                </button>
                <button
                  onClick={() => rateFlip('good')}
                  className="py-3 min-h-[44px] rounded-xl border-2 border-primary bg-primary/5 text-primary font-medium hover:bg-primary/10 transition-colors"
                >
                  🙂 {t('review.flip.good')}
                  <div className="text-xs opacity-75">(2)</div>
                </button>
                <button
                  onClick={() => rateFlip('easy')}
                  className="py-3 min-h-[44px] rounded-xl border-2 border-success bg-success/5 text-success font-medium hover:bg-success/10 transition-colors"
                >
                  😎 {t('review.flip.easy')}
                  <div className="text-xs opacity-75">(3)</div>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  return null
}
