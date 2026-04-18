import { useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'
import {
  DictationDiffItem,
  ListeningExerciseResult,
  ListeningExerciseView,
} from '../lib/listening'

function DiffView({ items }: { items: DictationDiffItem[] }) {
  return (
    <div className="bg-surface-raised border border-border rounded-xl p-4 leading-relaxed">
      <h4 className="text-sm font-semibold text-fg mb-2">Kết quả so sánh</h4>
      <p className="flex flex-wrap gap-x-1 gap-y-1 text-base">
        {items.map((item, i) => {
          switch (item.type) {
            case 'correct':
              return (
                <span key={i} className="text-success">
                  {item.text}
                </span>
              )
            case 'wrong':
              return (
                <span key={i} className="text-danger line-through">
                  {item.text}
                  <span className="not-italic text-success ml-1">
                    ({item.expected})
                  </span>
                </span>
              )
            case 'missed':
              return (
                <span
                  key={i}
                  className="text-muted-fg italic underline decoration-dashed"
                  title="Bạn bỏ sót từ này"
                >
                  {item.text}
                </span>
              )
            case 'extra':
              return (
                <span
                  key={i}
                  className="text-accent line-through"
                  title="Từ thừa"
                >
                  {item.text}
                </span>
              )
          }
        })}
      </p>
      <div className="mt-3 flex gap-4 text-xs text-muted-fg">
        <span><span className="text-success">■</span> đúng</span>
        <span><span className="text-danger">■</span> sai</span>
        <span><span className="text-muted-fg">■</span> bỏ sót</span>
        <span><span className="text-accent">■</span> thừa</span>
      </div>
    </div>
  )
}

function MisheardBridge({ words }: { words: string[] }) {
  const [added, setAdded] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const addWord = async (word: string) => {
    setBusy(word)
    setError(null)
    try {
      await apiFetch('/api/v1/vocabulary', {
        method: 'POST',
        body: JSON.stringify({ word }),
      })
      setAdded((prev) => new Set(prev).add(word))
    } catch (e) {
      const msg = (e as Error).message
      if (msg.toLowerCase().includes('already')) {
        setAdded((prev) => new Set(prev).add(word))
      } else {
        setError(msg)
      }
    } finally {
      setBusy(null)
    }
  }

  if (words.length === 0) return null

  return (
    <div className="bg-warning/10 border border-warning/30 rounded-xl p-4">
      <h4 className="text-sm font-semibold text-warning mb-2">
        Từ bị nghe nhầm — thêm vào vocabulary?
      </h4>
      {error && (
        <p className="text-xs text-danger mb-2">{error}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {words.map((w) => {
          const isAdded = added.has(w)
          return (
            <button
              key={w}
              onClick={() => !isAdded && addWord(w)}
              disabled={isAdded || busy === w}
              className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                isAdded
                  ? 'bg-success/10 text-success border-success/30 cursor-default'
                  : 'bg-surface-raised text-warning border-warning/30 hover:bg-warning/20 disabled:opacity-60'
              }`}
            >
              {isAdded ? `✓ ${w}` : busy === w ? `${w}...` : `+ ${w}`}
            </button>
          )
        })}
      </div>
    </div>
  )
}

interface Props {
  exercise: ListeningExerciseView
  onSubmitted?: (result: ListeningExerciseResult) => void
}

export default function DictationExercise({ exercise, onSubmitted }: Props) {
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ListeningExerciseResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = useMemo(
    () => text.trim().length > 0 && !submitting && !result,
    [text, submitting, result],
  )

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await apiFetch<ListeningExerciseResult>(
        `/api/v1/listening/${exercise.id}/submit`,
        { method: 'POST', body: JSON.stringify({ user_text: text }) },
      )
      setResult(res)
      onSubmitted?.(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    return (
      <div className="space-y-4">
        <div className="bg-primary/10 border border-primary/20 rounded-xl p-4">
          <p className="text-sm text-fg">
            Điểm chính xác:{' '}
            <span className="font-semibold text-lg text-primary">
              {Math.round((result.score ?? 0) * 100)}%
            </span>
          </p>
        </div>
        <DiffView items={result.dictation_diff} />
        <MisheardBridge words={result.misheard_words} />
        <div className="bg-surface border border-border rounded-xl p-4">
          <h4 className="text-xs font-semibold text-muted-fg uppercase tracking-wide mb-1">
            Transcript
          </h4>
          <p className="text-fg">{result.transcript}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Nghe audio và gõ lại chính xác những gì bạn nghe được..."
        className="w-full min-h-[180px] p-4 bg-surface-raised rounded-xl border border-border focus:border-primary focus:outline-none text-fg leading-relaxed"
      />
      {error && (
        <p className="text-sm text-danger">{error}</p>
      )}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-fg">
          Bạn có thể nghe lại nhiều lần trước khi nộp.
        </p>
        <button
          onClick={submit}
          disabled={!canSubmit}
          className="px-6 py-2 bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
        >
          {submitting ? 'Đang chấm...' : 'Nộp bài'}
        </button>
      </div>
    </div>
  )
}
