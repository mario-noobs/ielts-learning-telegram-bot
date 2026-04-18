import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { clearDraft, formatTimeVi, loadDraft, useAutosave } from '../lib/autosave'
import { useReducedMotion } from '../lib/motion'
import {
  AnnotatedEssay,
  ScorePanel,
  VietnameseSummary,
} from '../components/WritingFeedback'
import SubmissionSkeleton from '../components/SubmissionSkeleton'
import WritingDiff from '../components/WritingDiff'
import TaskVisualization from '../components/TaskVisualization'
import {
  countWords,
  formatDuration,
  Task1Visualization,
  TaskPromptResponse,
  TaskType,
  WritingSubmission,
} from '../lib/writing'

interface UserProfile {
  target_band: number
}

const MIN_WORDS = 20
const IELTS_WORD_TARGET: Record<TaskType, number> = { task1: 150, task2: 250 }

function draftKey(taskType: TaskType, reviseOf: string | null): string {
  return `writing_draft_${taskType}_${reviseOf ?? 'new'}`
}

function TaskSelector({
  value,
  onChange,
  disabled,
}: {
  value: TaskType
  onChange: (t: TaskType) => void
  disabled?: boolean
}) {
  const options: { key: TaskType; label: string }[] = [
    { key: 'task1', label: 'Task 1' },
    { key: 'task2', label: 'Task 2' },
  ]
  return (
    <div className="inline-flex rounded-lg border border-border bg-surface-raised overflow-hidden">
      {options.map((o) => (
        <button
          key={o.key}
          disabled={disabled}
          onClick={() => onChange(o.key)}
          className={`px-4 py-1.5 text-sm font-medium ${
            value === o.key
              ? 'bg-primary text-primary-fg'
              : 'text-fg hover:bg-surface'
          } disabled:opacity-50`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function PromptCard({
  prompt,
  typewriter,
  loading,
  onGenerate,
  visualization,
}: {
  prompt: string
  typewriter: string
  loading: boolean
  onGenerate: () => void
  visualization: Task1Visualization | null
}) {
  const display = loading || !prompt ? typewriter : prompt
  return (
    <div className="space-y-3">
      <div className="bg-primary/10 border border-primary/20 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-primary uppercase tracking-wide">
            Đề bài
          </h2>
          <button
            onClick={onGenerate}
            disabled={loading}
            className="text-xs text-primary hover:text-primary-hover underline disabled:opacity-50"
          >
            {prompt ? 'Đề khác' : 'Tạo đề'}
          </button>
        </div>
        <p className="text-fg whitespace-pre-line min-h-[3rem]">
          {display || 'Chưa có đề. Bấm "Tạo đề" để bắt đầu.'}
        </p>
      </div>
      {visualization && prompt && <TaskVisualization viz={visualization} />}
    </div>
  )
}

export default function WritingPage() {
  const [searchParams] = useSearchParams()
  const reviseOf = searchParams.get('reviseOf')

  const [taskType, setTaskType] = useState<TaskType>('task2')

  type TaskState = {
    prompt: string
    typewriter: string
    visualization: Task1Visualization | null
    text: string
  }
  const emptyTaskState: TaskState = {
    prompt: '', typewriter: '', visualization: null, text: '',
  }
  const [tasks, setTasks] = useState<Record<TaskType, TaskState>>({
    task1: { ...emptyTaskState },
    task2: { ...emptyTaskState },
  })

  const patchTask = (t: TaskType, patch: Partial<TaskState>) => {
    setTasks((prev) => ({ ...prev, [t]: { ...prev[t], ...patch } }))
  }

  const { prompt, typewriter, visualization, text } = tasks[taskType]

  const [promptLoading, setPromptLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [now, setNow] = useState<number>(Date.now())
  const [submission, setSubmission] = useState<WritingSubmission | null>(null)
  const [originalForDiff, setOriginalForDiff] = useState<WritingSubmission | null>(null)
  const [targetBand, setTargetBand] = useState<number>(7.0)
  const [draftSavedAt, setDraftSavedAt] = useState<number | null>(null)
  const reducedMotion = useReducedMotion()

  const typeIntervalRef = useRef<number | null>(null)

  const currentDraftKey = draftKey(taskType, reviseOf)

  // Restore draft on mount / when switching task type (only for fresh writes)
  useEffect(() => {
    if (reviseOf) return // revise flow loads from server
    const draft = loadDraft<{ prompt: string; text: string; visualization: Task1Visualization | null }>(
      draftKey(taskType, null),
    )
    if (!draft) return
    const ageHours = (Date.now() - draft.savedAt) / 3_600_000
    if (ageHours > 24) return // too old, skip
    patchTask(taskType, {
      prompt: draft.value.prompt || '',
      typewriter: draft.value.prompt || '',
      text: draft.value.text || '',
      visualization: draft.value.visualization || null,
    })
    setDraftSavedAt(draft.savedAt)
  }, [taskType, reviseOf])

  // Autosave every 5s while composing
  const onSaved = useCallback((ts: number) => setDraftSavedAt(ts), [])
  useAutosave(
    currentDraftKey,
    { prompt, text, visualization },
    5000,
    onSaved,
  )

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setTargetBand(p.target_band))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!reviseOf) return
    apiFetch<WritingSubmission>(`/api/v1/writing/${reviseOf}`)
      .then((res) => {
        setOriginalForDiff(res)
        setTaskType(res.task_type)
        patchTask(res.task_type, {
          prompt: res.prompt,
          typewriter: res.prompt,
          text: res.text,
        })
      })
      .catch((e) => setError((e as Error).message))
  }, [reviseOf])

  useEffect(() => {
    if (!startedAt || submission) return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [startedAt, submission])

  const wordCount = useMemo(() => countWords(text), [text])
  const canSubmit = wordCount >= MIN_WORDS && !submitting
  const elapsed = startedAt
    ? Math.floor(((submission ? Date.parse(submission.created_at || '') : now) - startedAt) / 1000)
    : 0

  const generatePrompt = async () => {
    const t = taskType
    setPromptLoading(true)
    setError(null)
    patchTask(t, { prompt: '', typewriter: '', visualization: null })
    try {
      const res = await apiFetch<TaskPromptResponse>('/api/v1/writing/prompt', {
        method: 'POST',
        body: JSON.stringify({ task_type: t }),
      })
      if (typeIntervalRef.current) window.clearInterval(typeIntervalRef.current)
      if (reducedMotion) {
        // Reduced motion: show prompt instantly, no typewriter
        patchTask(t, { typewriter: res.prompt, prompt: res.prompt, visualization: res.visualization })
      } else {
        let i = 0
        typeIntervalRef.current = window.setInterval(() => {
          i += 2
          patchTask(t, { typewriter: res.prompt.slice(0, i) })
          if (i >= res.prompt.length) {
            window.clearInterval(typeIntervalRef.current!)
            typeIntervalRef.current = null
            patchTask(t, { prompt: res.prompt, visualization: res.visualization })
          }
        }, 15)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPromptLoading(false)
    }
  }

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const path = reviseOf
        ? `/api/v1/writing/${reviseOf}/revise`
        : '/api/v1/writing/submit'
      const body = reviseOf
        ? JSON.stringify({ text })
        : JSON.stringify({ text, task_type: taskType, prompt })
      const res = await apiFetch<WritingSubmission>(path, { method: 'POST', body })
      setSubmission(res)
      clearDraft(currentDraftKey)
      setDraftSavedAt(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (submission) {
    const delta = submission.delta_band
    return (
      <div className="max-w-3xl mx-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <Link to="/write/history" className="text-sm text-muted-fg hover:text-fg">
            Lịch sử bài viết
          </Link>
          <Link
            to="/write"
            className="text-sm text-primary hover:text-primary-hover font-medium"
          >
            Viết bài mới
          </Link>
        </div>
        {delta !== null && delta !== undefined && (
          <div
            className={`rounded-xl p-4 ${
              delta >= 0
                ? 'bg-success/10 border-l-4 border-success'
                : 'bg-danger/10 border-l-4 border-danger'
            }`}
          >
            <p className="font-medium text-fg">
              Thay đổi so với bản gốc:{' '}
              <span className={delta >= 0 ? 'text-success' : 'text-danger'}>
                {delta > 0 ? '+' : ''}
                {delta.toFixed(1)} band
              </span>
            </p>
          </div>
        )}
        <ScorePanel submission={submission} targetBand={targetBand} />
        <VietnameseSummary summary={submission.summary_vi} />
        {originalForDiff && (
          <WritingDiff original={originalForDiff.text} revised={submission.text} />
        )}
        <AnnotatedEssay submission={submission} />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-end gap-3 text-sm text-muted-fg">
        <span className="font-mono tabular-nums">{formatDuration(elapsed)}</span>
        <span>
          <span className={wordCount < MIN_WORDS ? 'text-danger' : 'text-success'}>
            {wordCount}
          </span>{' '}
          từ
        </span>
      </div>

      <div className="flex items-center gap-3">
        <TaskSelector
          value={taskType}
          onChange={setTaskType}
          disabled={!!startedAt}
        />
      </div>

      <PromptCard
        prompt={prompt}
        typewriter={typewriter}
        loading={promptLoading}
        onGenerate={generatePrompt}
        visualization={visualization}
      />

      {error && (
        <div role="alert" className="bg-danger/10 border-l-4 border-danger p-3 rounded text-danger text-sm">
          {error}
        </div>
      )}

      {submitting && <SubmissionSkeleton />}

      {!submitting && (
        <>
          <textarea
            value={text}
            onChange={(e) => {
              patchTask(taskType, { text: e.target.value })
              if (!startedAt && e.target.value.length > 0) setStartedAt(Date.now())
            }}
            disabled={submitting}
            placeholder="Bắt đầu viết tại đây..."
            aria-label="Nội dung bài viết"
            className="w-full min-h-[360px] p-4 bg-surface-raised rounded-xl border border-border focus:border-primary focus:outline-none text-fg leading-relaxed disabled:opacity-60"
          />

          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-fg">
              {draftSavedAt ? `Đã lưu nháp lúc ${formatTimeVi(draftSavedAt)}` : `Tự động lưu nháp sau ${MIN_WORDS} từ.`}
            </span>
            <WordTargetIndicator words={wordCount} target={IELTS_WORD_TARGET[taskType]} />
          </div>

          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-fg">
              Tối thiểu {MIN_WORDS} từ để nộp bài.
            </p>
            <button
              onClick={submit}
              disabled={!canSubmit}
              className="px-6 py-2 min-h-[44px] bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
            >
              Nộp bài
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function WordTargetIndicator({ words, target }: { words: number; target: number }) {
  const pct = Math.min(100, (words / target) * 100)
  const status =
    pct >= 100 ? 'success' : pct >= 50 ? 'warning' : 'danger'
  const message =
    pct >= 100
      ? `Đạt mục tiêu ${target} từ`
      : `${target - words} từ nữa đạt mục tiêu ${target}`
  const barClass = status === 'success' ? 'bg-success' : status === 'warning' ? 'bg-warning' : 'bg-danger'
  const textClass = status === 'success' ? 'text-success' : status === 'warning' ? 'text-warning' : 'text-danger'
  return (
    <div className="flex items-center gap-2">
      <span className={`tabular-nums ${textClass}`}>{message}</span>
      <div className="w-20 h-1.5 bg-border rounded-full overflow-hidden" aria-hidden>
        <div className={`h-full ${barClass} transition-[width] duration-slow`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
