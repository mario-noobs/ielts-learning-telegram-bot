import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'
import { apiFetch } from '../lib/api'

interface QuizQuestion {
  id: string
  type: string
  question: string
  options: string[]
  word_id: string
}

interface QuizStartResponse {
  session_id: string
  questions: QuizQuestion[]
}

interface SRSUpdate {
  next_review: string | null
  old_strength: string
  new_strength: string
  strength_change: boolean
}

interface QuizAnswerResponse {
  is_correct: boolean
  feedback: string
  srs_update: SRSUpdate
}

interface AnswerRecord {
  question: QuizQuestion
  answer: string
  result: QuizAnswerResponse
}

type Phase = 'pre' | 'question' | 'feedback' | 'summary'

function formatNextReview(iso: string | null): string {
  if (!iso) return '—'
  const diffMs = new Date(iso).getTime() - Date.now()
  const diffMin = Math.round(diffMs / 60000)
  if (diffMin <= 0) return 'ngay bây giờ'
  if (diffMin < 60) return `trong ${diffMin} phút`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `trong ${diffHr} giờ`
  const diffDay = Math.round(diffHr / 24)
  return `trong ${diffDay} ngày`
}

function ProgressBar({ current, total }: { current: number; total: number }) {
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
        aria-label={`Câu ${current} trên ${total}`}
      >
        <div
          className="h-full bg-primary transition-[width] duration-slow ease-out-soft"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function MultipleChoice({
  question,
  onSubmit,
}: {
  question: QuizQuestion
  onSubmit: (letter: string) => void
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const k = parseInt(e.key, 10)
      if (k >= 1 && k <= question.options.length) {
        onSubmit(String.fromCharCode(65 + k - 1))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [question, onSubmit])

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {question.options.map((opt, i) => {
          const letter = String.fromCharCode(65 + i)
          return (
            <button
              key={letter}
              onClick={() => onSubmit(letter)}
              aria-label={`Đáp án ${letter}: ${opt}`}
              className="text-left p-4 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised hover:border-primary hover:bg-primary/5 transition-colors duration-base"
            >
              <span className="font-semibold text-primary mr-2">{letter}.</span>
              {opt}
            </button>
          )
        })}
      </div>
      <p className="text-xs text-muted-fg mt-3 text-center">
        Mẹo: bấm phím {question.options.map((_, i) => i + 1).join(' / ')} trên bàn phím
      </p>
    </>
  )
}

function FillBlank({ onSubmit }: { onSubmit: (text: string) => void }) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    inputRef.current?.focus()
  }, [])
  const submit = () => {
    if (value.trim()) onSubmit(value.trim())
  }
  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') submit()
        }}
        aria-label="Điền từ thích hợp"
        className="w-full px-4 py-3 min-h-[44px] border-2 border-border bg-surface-raised rounded-xl focus:border-primary focus:outline-none"
        placeholder="Ví dụ: abandon"
      />
      <button
        onClick={submit}
        disabled={!value.trim()}
        className="w-full px-4 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        Gửi
      </button>
    </div>
  )
}

function FeedbackOverlay({
  result,
  onContinue,
  isLast,
}: {
  result: QuizAnswerResponse
  onContinue: () => void
  isLast: boolean
}) {
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
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
    >
      <div className="bg-surface-raised dark:bg-surface rounded-2xl p-6 max-w-md w-full shadow-xl">
        <div className="flex items-center gap-3 mb-3">
          <Icon
            name={result.is_correct ? 'CheckCircle2' : 'AlertCircle'}
            size="xl"
            variant={result.is_correct ? 'success' : 'danger'}
            label={result.is_correct ? 'Đúng' : 'Sai'}
          />
          <h2 id="feedback-title" className={`text-2xl font-bold ${result.is_correct ? 'text-success' : 'text-danger'}`}>
            {result.is_correct ? 'Đúng rồi!' : 'Chưa đúng'}
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
          {isLast ? 'Xem kết quả' : 'Tiếp tục'} (Space)
        </button>
      </div>
    </div>
  )
}

function SessionSummary({
  records,
  onRestart,
}: {
  records: AnswerRecord[]
  onRestart: () => void
}) {
  const correct = records.filter((r) => r.result.is_correct).length
  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="bg-white rounded-xl shadow-sm p-6 text-center">
        <h2 className="text-sm uppercase tracking-wide text-gray-500 mb-2">Kết quả</h2>
        <div className="text-5xl font-bold text-blue-600">
          {correct}
          <span className="text-2xl text-gray-400">/{records.length}</span>
        </div>
      </div>
      <div className="space-y-2">
        {records.map((r, i) => (
          <div key={i} className="bg-white rounded-lg p-3 flex items-center justify-between text-sm">
            <div className="flex items-center gap-3">
              <span
                className={
                  r.result.is_correct ? 'text-green-600 font-bold' : 'text-red-600 font-bold'
                }
              >
                {r.result.is_correct ? '✓' : '✗'}
              </span>
              <span className="text-gray-700 truncate max-w-[180px]">{r.question.question}</span>
            </div>
            <div className="text-xs text-gray-500">
              {r.result.srs_update.old_strength} → {r.result.srs_update.new_strength} ·{' '}
              {formatNextReview(r.result.srs_update.next_review)}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-3">
        <button
          onClick={onRestart}
          className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700"
        >
          Ôn tiếp
        </button>
        <Link
          to="/vocab"
          className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-xl font-medium hover:bg-gray-200 text-center"
        >
          Về từ vựng
        </Link>
      </div>
    </div>
  )
}

export default function FlashcardReviewPage() {
  const [phase, setPhase] = useState<Phase>('pre')
  const [sessionId, setSessionId] = useState<string>('')
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [records, setRecords] = useState<AnswerRecord[]>([])
  const [feedback, setFeedback] = useState<QuizAnswerResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<QuizStartResponse>('/api/v1/quiz/start', {
        method: 'POST',
        body: JSON.stringify({ count: 10 }),
      })
      const supported = res.questions.filter(
        (q) => q.type === 'multiple_choice' || q.type === 'fill_blank'
      )
      if (supported.length === 0) {
        setError('Không có câu hỏi nào khả dụng.')
        setLoading(false)
        return
      }
      setSessionId(res.session_id)
      setQuestions(supported)
      setIndex(0)
      setRecords([])
      setPhase('question')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  const submit = useCallback(
    async (answer: string) => {
      const q = questions[index]
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
      }
    },
    [questions, index, sessionId]
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

  if (phase === 'pre') {
    if (error && error.toLowerCase().includes('enough')) {
      return (
        <div className="max-w-lg mx-auto p-4">
          <EmptyState
            illustration="empty-vocab"
            title="Chưa có từ đến hạn ôn"
            description="Thêm từ vựng mới hoặc chờ SRS nhắc lại trong vài giờ tới."
            primaryAction={{ label: 'Thêm từ vựng', to: '/vocab' }}
          />
        </div>
      )
    }
    return (
      <div className="max-w-lg mx-auto p-4">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h1 className="text-2xl font-bold mb-2">Ôn tập Flashcard</h1>
          <p className="text-gray-600 mb-6">
            Ôn lại từ đến hạn bằng câu hỏi trắc nghiệm và điền vào chỗ trống.
          </p>
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded mb-4 text-red-700 text-sm">
              {error}
            </div>
          )}
          <button
            onClick={start}
            disabled={loading}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Đang tải...' : 'Bắt đầu'}
          </button>
        </div>
      </div>
    )
  }

  if (phase === 'summary') {
    return <SessionSummary records={records} onRestart={start} />
  }

  if (!currentQuestion) return null

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/vocab" className="text-sm text-gray-500 hover:text-gray-700">
          Thoát
        </Link>
      </div>
      <ProgressBar current={index + 1} total={questions.length} />
      <div className="bg-white rounded-xl shadow-sm p-6">
        <p className="text-xl text-gray-900 mb-6 whitespace-pre-line">
          {currentQuestion.question}
        </p>
        {currentQuestion.type === 'multiple_choice' ? (
          <MultipleChoice question={currentQuestion} onSubmit={submit} />
        ) : (
          <FillBlank onSubmit={submit} />
        )}
      </div>
      {phase === 'feedback' && feedback && (
        <FeedbackOverlay
          result={feedback}
          onContinue={advance}
          isLast={index + 1 >= questions.length}
        />
      )}
    </div>
  )
}
