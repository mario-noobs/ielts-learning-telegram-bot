import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Icon from '../components/Icon'
import {
  PassageDetail,
  QUESTION_TYPE_LABEL,
  ReadingQuestion,
  ReadingSession,
  SessionSubmitResponse,
  clearHighlights,
  formatTimer,
  getPassage,
  loadHighlights,
  saveHighlights,
  startSession,
  submitSession,
} from '../lib/reading'

type ViewTab = 'passage' | 'questions'
type PageStatus = 'loading' | 'ready' | 'submitting' | 'submitted' | 'error'

export default function ReadingExercisePage() {
  const { id = '' } = useParams<{ id: string }>()
  const [passage, setPassage] = useState<PassageDetail | null>(null)
  const [session, setSession] = useState<ReadingSession | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [remaining, setRemaining] = useState<number>(20 * 60)
  const [status, setStatus] = useState<PageStatus>('loading')
  const [result, setResult] = useState<SessionSubmitResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [highlights, setHighlights] = useState<string[]>([])
  const [tab, setTab] = useState<ViewTab>('passage')
  const [showConfirm, setShowConfirm] = useState(false)
  const idempotencyRef = useRef<string>(
    `reading-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  )

  // ─── Load passage + start session ───────────────────────────────────
  useEffect(() => {
    if (!id) return
    setStatus('loading')
    Promise.all([getPassage(id), startSession(id)])
      .then(([p, s]) => {
        setPassage(p)
        setSession(s)
        setHighlights(loadHighlights(s.id))
        const deadline = new Date(s.expires_at).getTime()
        setRemaining(Math.max(0, Math.round((deadline - Date.now()) / 1000)))
        setStatus('ready')
      })
      .catch((e) => {
        setError((e as Error).message)
        setStatus('error')
      })
  }, [id])

  // ─── Timer ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (status !== 'ready' || !session) return
    const deadline = new Date(session.expires_at).getTime()
    const tick = () => {
      const secs = Math.max(0, Math.round((deadline - Date.now()) / 1000))
      setRemaining(secs)
      if (secs <= 0) {
        // AC2: auto-submit on zero — no confirmation.
        void doSubmit(true)
      }
    }
    tick()
    const h = setInterval(tick, 1000)
    return () => clearInterval(h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, session])

  // ─── Answers ────────────────────────────────────────────────────────
  const setAnswer = (qid: string, value: string) =>
    setAnswers((prev) => ({ ...prev, [qid]: value }))

  const answeredCount = Object.keys(answers).filter((k) => answers[k]?.trim()).length
  const totalCount = session?.questions.length ?? 0

  const doSubmit = useCallback(
    async (fromTimer = false) => {
      if (!session) return
      if (status === 'submitting' || status === 'submitted') return
      setStatus('submitting')
      setShowConfirm(false)
      try {
        const res = await submitSession(session.id, answers, idempotencyRef.current)
        setResult(res)
        setStatus('submitted')
        clearHighlights(session.id)
      } catch (e) {
        setError((e as Error).message)
        setStatus(fromTimer ? 'submitted' : 'ready')
      }
    },
    [answers, session, status],
  )

  // ─── Highlighting ──────────────────────────────────────────────────
  const addHighlight = (text: string) => {
    if (!session || !text.trim()) return
    const cleaned = text.trim()
    if (highlights.includes(cleaned)) return
    const next = [...highlights, cleaned]
    setHighlights(next)
    saveHighlights(session.id, next)
  }

  const clearAllHighlights = () => {
    if (!session) return
    setHighlights([])
    clearHighlights(session.id)
  }

  const onPassageMouseUp = () => {
    if (status !== 'ready') return
    const selection = window.getSelection?.()
    if (!selection || selection.isCollapsed) return
    const text = selection.toString()
    if (text.length >= 3 && text.length <= 240) addHighlight(text)
  }

  // ─── Render ─────────────────────────────────────────────────────────

  if (status === 'loading') {
    return (
      <div className="mx-auto max-w-6xl p-4 md:p-6">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="h-[60vh] animate-pulse rounded-xl bg-surface" />
          <div className="h-[60vh] animate-pulse rounded-xl bg-surface" />
        </div>
      </div>
    )
  }

  if (status === 'error' || !passage || !session) {
    return (
      <div className="mx-auto max-w-2xl p-4">
        <Link to="/reading" className="text-sm text-muted-fg hover:text-fg">
          ← Reading Lab
        </Link>
        <div className="mt-3 rounded border-l-4 border-danger bg-danger/10 p-3 text-sm text-danger">
          {error ?? 'Không tải được bài đọc.'}
        </div>
      </div>
    )
  }

  if (status === 'submitted' && result) {
    return <ReviewView result={result} passage={passage} />
  }

  const timerUrgent = remaining <= 5 * 60

  return (
    <div className="mx-auto max-w-6xl p-4 md:p-6">
      {/* Header with timer + submit */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Link to="/reading" className="text-sm text-muted-fg hover:text-fg">
          ← Reading Lab
        </Link>
        <div className="flex items-center gap-3">
          <span
            aria-live="polite"
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-sm font-semibold ${
              timerUrgent
                ? 'bg-danger/10 text-danger'
                : 'bg-surface-raised text-fg border border-border'
            }`}
          >
            <Icon name="Hourglass" size="sm" variant={timerUrgent ? 'danger' : 'muted'} />
            {formatTimer(remaining)}
          </span>
          <button
            onClick={() => setShowConfirm(true)}
            disabled={status !== 'ready'}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-fg hover:bg-primary-hover disabled:opacity-50"
          >
            Nộp bài ({answeredCount}/{totalCount})
          </button>
        </div>
      </div>

      {/* Mobile tabs */}
      <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg border border-border bg-surface-raised p-1 lg:hidden">
        {(['passage', 'questions'] as ViewTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-2 text-sm font-medium ${
              tab === t ? 'bg-primary text-primary-fg' : 'text-fg'
            }`}
          >
            {t === 'passage' ? 'Bài đọc' : `Câu hỏi (${answeredCount}/${totalCount})`}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Passage */}
        <section
          aria-labelledby="passage-heading"
          className={`${tab === 'passage' ? '' : 'hidden'} rounded-xl border border-border bg-surface-raised p-4 lg:block lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto`}
        >
          <header className="mb-3 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h1 id="passage-heading" className="text-lg font-bold text-fg">
                {passage.title}
              </h1>
              <p className="text-xs text-muted-fg">
                <span className="capitalize">{passage.topic}</span> · Band {passage.band.toFixed(1)} · {passage.word_count} từ
              </p>
            </div>
            {highlights.length > 0 && (
              <button
                onClick={clearAllHighlights}
                className="shrink-0 text-xs text-muted-fg underline hover:text-fg"
              >
                Xóa tô sáng ({highlights.length})
              </button>
            )}
          </header>
          <div
            onMouseUp={onPassageMouseUp}
            className="prose-reading space-y-3 text-base leading-relaxed text-fg"
          >
            {splitParagraphs(passage.body).map((para, i) => (
              <p key={i}>{renderWithHighlights(para, highlights)}</p>
            ))}
          </div>
          <p className="mt-4 text-[11px] text-muted-fg/70">{passage.attribution}</p>
        </section>

        {/* Questions */}
        <section
          aria-labelledby="questions-heading"
          className={`${tab === 'questions' ? '' : 'hidden'} rounded-xl border border-border bg-surface-raised p-4 lg:block lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto`}
        >
          <h2 id="questions-heading" className="mb-3 text-sm font-semibold text-muted-fg">
            Câu hỏi · {answeredCount}/{totalCount} đã trả lời
          </h2>
          <ol className="space-y-4">
            {session.questions.map((q, idx) => (
              <QuestionItem
                key={q.id}
                q={q}
                index={idx + 1}
                value={answers[q.id] ?? ''}
                onChange={(v) => setAnswer(q.id, v)}
              />
            ))}
          </ol>
        </section>
      </div>

      {/* Confirm submit modal (AC2) */}
      {showConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="submit-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        >
          <div className="w-full max-w-sm rounded-xl bg-surface-raised p-4 shadow-lg">
            <h3 id="submit-dialog-title" className="text-base font-semibold text-fg">
              Nộp bài ngay?
            </h3>
            <p className="mt-1 text-sm text-muted-fg">
              Bạn đã trả lời {answeredCount} / {totalCount} câu. Sau khi nộp, bạn không thể quay lại.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setShowConfirm(false)}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-fg hover:bg-surface-raised"
              >
                Tiếp tục làm
              </button>
              <button
                onClick={() => void doSubmit()}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-fg hover:bg-primary-hover"
              >
                Nộp bài
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────

function splitParagraphs(body: string): string[] {
  return body.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)
}

/**
 * Wrap every occurrence of any highlighted string in `<mark>`. Matching is
 * case-sensitive and literal. Overlaps use first-match-wins ordering; good
 * enough for the read + highlight flow in M9.4.
 */
function renderWithHighlights(text: string, highlights: string[]): React.ReactNode {
  if (highlights.length === 0) return text
  const parts: Array<string | { hl: string }> = [text]
  for (const hl of highlights) {
    if (!hl) continue
    const next: typeof parts = []
    for (const part of parts) {
      if (typeof part !== 'string') {
        next.push(part)
        continue
      }
      let rest = part
      while (rest) {
        const idx = rest.indexOf(hl)
        if (idx === -1) {
          next.push(rest)
          break
        }
        if (idx > 0) next.push(rest.slice(0, idx))
        next.push({ hl })
        rest = rest.slice(idx + hl.length)
      }
    }
    parts.length = 0
    parts.push(...next)
  }
  return parts.map((p, i) =>
    typeof p === 'string'
      ? p
      : <mark key={i} className="rounded bg-warning/30 px-0.5">{p.hl}</mark>,
  )
}

// ─── Question renderer ────────────────────────────────────────────────

interface QuestionItemProps {
  q: ReadingQuestion
  index: number
  value: string
  onChange: (v: string) => void
}

function QuestionItem({ q, index, value, onChange }: QuestionItemProps) {
  return (
    <li className="rounded-lg border border-border p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
          {index}
        </span>
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-fg">
          {QUESTION_TYPE_LABEL[q.type]}
        </span>
      </div>
      <p className="text-sm text-fg">{q.stem}</p>
      <div className="mt-2">
        {q.type === 'gap-fill' && (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Nhập đáp án"
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
        )}
        {q.type === 'tfng' && (
          <div className="flex flex-wrap gap-2">
            {(['TRUE', 'FALSE', 'NOT_GIVEN'] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => onChange(v)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  value === v
                    ? 'border-primary bg-primary text-primary-fg'
                    : 'border-border bg-surface text-fg hover:bg-surface-raised'
                }`}
              >
                {v === 'TRUE' ? 'Đúng' : v === 'FALSE' ? 'Sai' : 'Không rõ'}
              </button>
            ))}
          </div>
        )}
        {(q.type === 'mcq' || q.type === 'matching-headings') && q.options && (
          <div className="space-y-1">
            {q.options.map((o) => (
              <label
                key={o.id}
                className={`flex cursor-pointer items-start gap-2 rounded-lg border p-2 text-sm transition-colors ${
                  value === o.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border bg-surface hover:bg-surface-raised'
                }`}
              >
                <input
                  type="radio"
                  name={q.id}
                  value={o.id}
                  checked={value === o.id}
                  onChange={() => onChange(o.id)}
                  className="mt-0.5"
                />
                <span className="flex-1 text-fg">{o.text}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    </li>
  )
}

// ─── Review view (post-submit) ────────────────────────────────────────

function ReviewView({
  result,
  passage,
}: {
  result: SessionSubmitResponse
  passage: PassageDetail
}) {
  const { grade } = result
  const pct = grade.total > 0 ? Math.round((grade.correct / grade.total) * 100) : 0

  return (
    <div className="mx-auto max-w-3xl p-4 md:p-6 space-y-4">
      <Link to="/reading" className="text-sm text-muted-fg hover:text-fg">
        ← Reading Lab
      </Link>

      <section className="rounded-2xl border border-border bg-surface-raised p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-fg">
          Kết quả · {passage.title}
        </p>
        <div className="mt-2 flex items-end gap-4">
          <div>
            <p className="text-5xl font-bold text-fg">{grade.band.toFixed(1)}</p>
            <p className="text-xs text-muted-fg">Band ước lượng</p>
          </div>
          <div className="flex-1 text-right">
            <p className="text-2xl font-semibold text-fg">
              {grade.correct} / {grade.total}
            </p>
            <p className="text-xs text-muted-fg">Đúng ({pct}%)</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="per-question-heading" className="space-y-2">
        <h2 id="per-question-heading" className="text-sm font-semibold text-fg">
          Chi tiết từng câu
        </h2>
        <ol className="space-y-2">
          {grade.per_question.map((pq, i) => (
            <li
              key={pq.id}
              className={`rounded-lg border p-3 text-sm ${
                pq.is_correct
                  ? 'border-success/30 bg-success/5'
                  : 'border-danger/30 bg-danger/5'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-surface text-xs font-bold text-fg">
                  {i + 1}
                </span>
                <span className={`text-xs font-semibold ${
                  pq.is_correct ? 'text-success' : 'text-danger'
                }`}>
                  {pq.is_correct ? 'Đúng' : 'Sai'}
                </span>
              </div>
              <div className="mt-1 grid gap-1 sm:grid-cols-2">
                <p className="text-xs text-muted-fg">
                  Đáp án của bạn: <span className="font-medium text-fg">{pq.user_answer ?? '(bỏ trống)'}</span>
                </p>
                <p className="text-xs text-muted-fg">
                  Đáp án đúng: <span className="font-medium text-fg">{pq.correct_answer}</span>
                </p>
              </div>
              {pq.explanation && (
                <p className="mt-1 text-xs text-fg">{pq.explanation}</p>
              )}
            </li>
          ))}
        </ol>
      </section>

      <div className="flex justify-center gap-2">
        <Link
          to="/reading"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-fg hover:bg-primary-hover"
        >
          Bài đọc khác
        </Link>
        <Link
          to="/progress"
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-fg hover:bg-surface-raised"
        >
          Xem tiến độ
        </Link>
      </div>
    </div>
  )
}
