import { useMemo, useRef, useState } from 'react'
import { apiFetch } from '../lib/api'
import {
  GapFillResultItem,
  ListeningExerciseResult,
  ListeningExerciseView,
} from '../lib/listening'

const BLANK_TOKEN = '_____'

interface Props {
  exercise: ListeningExerciseView
  onSubmitted?: (result: ListeningExerciseResult) => void
}

export default function GapFillExercise({ exercise, onSubmitted }: Props) {
  const segments = useMemo(
    () => exercise.display_text.split(BLANK_TOKEN),
    [exercise.display_text],
  )
  const blankCount = Math.max(0, segments.length - 1)
  const [answers, setAnswers] = useState<string[]>(() => Array(blankCount).fill(''))
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ListeningExerciseResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  const canSubmit =
    !submitting && !result && answers.some((a) => a.trim().length > 0)

  const setAnswer = (i: number, v: string) => {
    setAnswers((prev) => {
      const next = [...prev]
      next[i] = v
      return next
    })
  }

  const onKeyDown = (i: number) => (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const next = inputRefs.current[i + 1]
      if (next) next.focus()
      else submit()
    }
  }

  const submit = async () => {
    if (submitting || result) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await apiFetch<ListeningExerciseResult>(
        `/api/v1/listening/${exercise.id}/submit`,
        {
          method: 'POST',
          body: JSON.stringify({ answers }),
        },
      )
      setResult(res)
      onSubmitted?.(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const resultByIndex = useMemo(() => {
    const map = new Map<number, GapFillResultItem>()
    for (const r of result?.gap_fill_results ?? []) map.set(r.index, r)
    return map
  }, [result])

  const renderBlank = (i: number) => {
    const r = resultByIndex.get(i)
    if (r) {
      const base = r.is_correct
        ? 'bg-success/10 border-success/50 text-success'
        : 'bg-danger/10 border-danger/50 text-danger'
      return (
        <span
          key={`b-${i}`}
          className={`inline-flex items-center gap-1 px-2 py-0.5 mx-1 rounded border ${base}`}
        >
          <span className={r.is_correct ? '' : 'line-through'}>
            {r.user_answer || '—'}
          </span>
          {!r.is_correct && (
            <span className="text-success font-semibold">
              {r.correct_answer}
            </span>
          )}
        </span>
      )
    }
    return (
      <input
        key={`b-${i}`}
        ref={(el) => {
          inputRefs.current[i] = el
        }}
        value={answers[i]}
        onChange={(e) => setAnswer(i, e.target.value)}
        onKeyDown={onKeyDown(i)}
        className="inline-block w-28 mx-1 px-2 py-0.5 bg-surface-raised border-b-2 border-primary/60 focus:border-primary focus:outline-none text-center text-fg"
        aria-label={`Blank ${i + 1}`}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="bg-surface-raised border border-border rounded-xl p-4 leading-loose text-fg whitespace-pre-line">
        {segments.map((seg, i) => (
          <span key={i}>
            {seg}
            {i < segments.length - 1 && renderBlank(i)}
          </span>
        ))}
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {result ? (
        <div className="bg-primary/10 border border-primary/20 rounded-xl p-4">
          <p className="text-sm text-fg">
            Đúng {result.gap_fill_results.filter((r) => r.is_correct).length}/
            {result.gap_fill_results.length} chỗ trống —{' '}
            <span className="font-semibold text-lg text-primary">
              {Math.round((result.score ?? 0) * 100)}%
            </span>
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-fg">
            Enter/Tab để sang ô tiếp theo.
          </p>
          <button
            onClick={submit}
            disabled={!canSubmit}
            className="px-6 py-2 bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
          >
            {submitting ? 'Đang chấm...' : 'Nộp bài'}
          </button>
        </div>
      )}
    </div>
  )
}
