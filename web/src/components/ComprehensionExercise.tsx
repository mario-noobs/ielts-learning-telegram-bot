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
            className="bg-white border border-gray-200 rounded-xl p-4 space-y-2"
          >
            <p className="font-medium text-gray-900">
              {qi + 1}. {q.question}
            </p>
            <div className="space-y-1.5">
              {q.options.map((opt, oi) => {
                const isChosen = chosen === oi
                const isCorrect = r && oi === r.correct_index
                const isWrongPick = r && isChosen && oi !== r.correct_index
                const base = r
                  ? isCorrect
                    ? 'bg-green-50 border-green-400 text-green-900'
                    : isWrongPick
                      ? 'bg-red-50 border-red-400 text-red-900'
                      : 'bg-white border-gray-200 text-gray-700'
                  : isChosen
                    ? 'bg-indigo-50 border-indigo-400 text-indigo-900'
                    : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
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
                  r.is_correct ? 'text-green-700' : 'text-red-700'
                }`}
              >
                {r.is_correct ? '✓ Chính xác' : '✗ Chưa đúng'}
                {r.explanation_vi && (
                  <span className="text-gray-600"> — {r.explanation_vi}</span>
                )}
              </p>
            )}
          </div>
        )
      })}

      {error && <p className="text-sm text-red-700">{error}</p>}

      {result ? (
        <div className="space-y-3">
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
            <p className="text-sm text-indigo-900">
              Đúng{' '}
              {result.comprehension_results.filter((r) => r.is_correct).length}/
              {result.comprehension_results.length} câu —{' '}
              <span className="font-semibold text-lg">
                {Math.round((result.score ?? 0) * 100)}%
              </span>
            </p>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
              Transcript
            </h4>
            <p className="text-gray-800 whitespace-pre-line">{result.transcript}</p>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-end">
          <button
            onClick={submit}
            disabled={!canSubmit}
            className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? 'Đang chấm...' : 'Nộp bài'}
          </button>
        </div>
      )}
    </div>
  )
}
