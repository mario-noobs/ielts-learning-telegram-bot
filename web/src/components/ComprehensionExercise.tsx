import { useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'
import {
  ComprehensionResultItem,
  ListeningExerciseResult,
  ListeningExerciseView,
} from '../lib/listening'

const OPTION_LABELS = ['A', 'B', 'C', 'D', 'E']

interface Props {
  exercise: ListeningExerciseView
  onSubmitted?: (result: ListeningExerciseResult) => void
}

export default function ComprehensionExercise({ exercise, onSubmitted }: Props) {
  const questions = exercise.questions
  const [selected, setSelected] = useState<Record<number, number>>({})
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ListeningExerciseResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canSubmit =
    !submitting && !result && Object.keys(selected).length === questions.length

  const pick = (qi: number, oi: number) => {
    if (result) return
    setSelected((prev) => ({ ...prev, [qi]: oi }))
  }

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const answers = questions.map((_, i) => String(selected[i] ?? -1))
      const res = await apiFetch<ListeningExerciseResult>(
        `/api/v1/listening/${exercise.id}/submit`,
        { method: 'POST', body: JSON.stringify({ answers }) },
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
    const map = new Map<number, ComprehensionResultItem>()
    for (const r of result?.comprehension_results ?? []) map.set(r.index, r)
    return map
  }, [result])

  return (
    <div className="space-y-4">
      {questions.map((q, qi) => {
        const chosen = selected[qi]
        const r = resultByIndex.get(qi)
        return (
          <div
            key={qi}
            className="bg-surface-raised border border-border rounded-xl p-4 space-y-2"
          >
            <p className="font-medium text-fg">
              {qi + 1}. {q.question}
            </p>
            <div className="space-y-1.5">
              {q.options.map((opt, oi) => {
                const isChosen = chosen === oi
                const isCorrect = r && oi === r.correct_index
                const isWrongPick = r && isChosen && oi !== r.correct_index
                const base = r
                  ? isCorrect
                    ? 'bg-success/10 border-success/50 text-success'
                    : isWrongPick
                      ? 'bg-danger/10 border-danger/50 text-danger'
                      : 'bg-surface-raised border-border text-fg'
                  : isChosen
                    ? 'bg-primary/10 border-primary/50 text-primary'
                    : 'bg-surface-raised border-border text-fg hover:bg-surface'
                return (
                  <button
                    key={oi}
                    onClick={() => pick(qi, oi)}
                    disabled={!!result}
                    className={`w-full text-left px-3 py-2 rounded-lg border ${base} flex items-center gap-3`}
                  >
                    <span className="w-6 h-6 rounded-full border border-current flex items-center justify-center text-xs font-semibold">
                      {OPTION_LABELS[oi] ?? oi + 1}
                    </span>
                    <span>{opt}</span>
                  </button>
                )
              })}
            </div>
            {r && (
              <p
                className={`text-sm ${
                  r.is_correct ? 'text-success' : 'text-danger'
                }`}
              >
                {r.is_correct ? '✓ Chính xác' : '✗ Chưa đúng'}
                {r.explanation_vi && (
                  <span className="text-muted-fg"> — {r.explanation_vi}</span>
                )}
              </p>
            )}
          </div>
        )
      })}

      {error && <p className="text-sm text-danger">{error}</p>}

      {result ? (
        <div className="space-y-3">
          <div className="bg-primary/10 border border-primary/20 rounded-xl p-4">
            <p className="text-sm text-fg">
              Đúng{' '}
              {result.comprehension_results.filter((r) => r.is_correct).length}/
              {result.comprehension_results.length} câu —{' '}
              <span className="font-semibold text-lg text-primary">
                {Math.round((result.score ?? 0) * 100)}%
              </span>
            </p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-4">
            <h4 className="text-xs font-semibold text-muted-fg uppercase tracking-wide mb-1">
              Transcript
            </h4>
            <p className="text-fg whitespace-pre-line">{result.transcript}</p>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-end">
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
