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

interface DailyWord {
  word: string
  word_id: string
}

interface DailyWordsResponse {
  date: string
  topic: string
  words: DailyWord[]
}

type Phase = 'loading' | 'error' | 'empty' | 'question' | 'feedback' | 'summary'

export default function DailyFillBlankPage() {
  const { t } = useTranslation('vocab')
  const [phase, setPhase] = useState<Phase>('loading')
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string>('')
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [records, setRecords] = useState<AnswerRecord[]>([])
  const [feedback, setFeedback] = useState<QuizAnswerResponse | null>(null)

  const begin = useCallback(async () => {
    setPhase('loading')
    setError(null)
    try {
      const daily = await apiFetch<DailyWordsResponse>(
        '/api/v1/vocabulary/daily',
        { method: 'POST' },
      )
      const wordIds = daily.words.map((w) => w.word_id).filter(Boolean)
      if (wordIds.length === 0) {
        setPhase('empty')
        return
      }
      const res = await apiFetch<QuizStartResponse>('/api/v1/quiz/start', {
        method: 'POST',
        body: JSON.stringify({
          count: wordIds.length,
          types: ['fill_blank'],
          word_ids: wordIds,
        }),
      })
      const supported = res.questions.filter((q) => q.type === 'fill_blank')
      if (supported.length === 0) {
        setPhase('empty')
        return
      }
      setSessionId(res.session_id)
      setQuestions(supported)
      setIndex(0)
      setRecords([])
      setPhase('question')
    } catch (e) {
      setError((e as Error).message)
      setPhase('error')
    }
  }, [])

  useEffect(() => {
    begin()
  }, [begin])

  const submit = useCallback(
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
        setPhase('feedback')
      } catch (e) {
        setError((e as Error).message)
        setPhase('error')
      }
    },
    [questions, index, sessionId],
  )

  const advance = useCallback(() => {
    if (index + 1 >= questions.length) {
      setPhase('summary')
    } else {
      setIndex((i) => i + 1)
      setPhase('question')
    }
    setFeedback(null)
  }, [index, questions.length])

  const currentQuestion = useMemo(() => questions[index], [questions, index])

  if (phase === 'loading') {
    return (
      <div className="max-w-2xl mx-auto p-4 text-center text-muted-fg">
        {t('daily.loading')}
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-3">
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg text-danger text-sm">
          {error}
        </div>
        <button
          onClick={begin}
          className="w-full py-3 bg-primary text-primary-fg rounded-xl font-medium hover:bg-primary-hover"
        >
          {t('daily.retry')}
        </button>
      </div>
    )
  }

  if (phase === 'empty') {
    return (
      <div className="max-w-lg mx-auto p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('daily.empty.title')}
          description={t('daily.empty.description')}
          primaryAction={{ label: t('daily.empty.cta'), to: '/daily' }}
        />
      </div>
    )
  }

  if (phase === 'summary') {
    return <QuizSessionSummary records={records} onRestart={begin} backTo="/daily" t={t} />
  }

  if (!currentQuestion) return null

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/daily" className="text-sm text-muted-fg hover:text-fg">
          {t('review.exit')}
        </Link>
        <span className="text-sm text-muted-fg tabular-nums">
          {index + 1} / {questions.length}
        </span>
      </div>
      <div className="bg-surface-raised rounded-xl shadow-sm p-6">
        <p className="text-xl text-fg mb-6 whitespace-pre-line">
          {currentQuestion.question}
        </p>
        <MultipleChoiceQuestion
          options={currentQuestion.options}
          onSubmit={submit}
          disabled={phase === 'feedback'}
          mcqOptionAria={(o) => t('review.mcqOptionAria', o)}
          keyboardHint={(keys) => t('review.keyboardHint', { keys })}
        />
      </div>
      {phase === 'feedback' && feedback && (
        <QuizFeedbackOverlay
          result={feedback}
          onContinue={advance}
          isLast={index + 1 >= questions.length}
          t={t}
        />
      )}
    </div>
  )
}
