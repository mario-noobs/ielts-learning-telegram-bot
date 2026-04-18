import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import {
  AnnotatedEssay,
  ScorePanel,
  VietnameseSummary,
} from '../components/WritingFeedback'
import {
  countWords,
  formatDuration,
  TaskType,
  WritingSubmission,
} from '../lib/writing'

interface UserProfile {
  target_band: number
}

const MIN_WORDS = 20

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
    <div className="inline-flex rounded-lg border border-gray-200 bg-white overflow-hidden">
      {options.map((o) => (
        <button
          key={o.key}
          disabled={disabled}
          onClick={() => onChange(o.key)}
          className={`px-4 py-1.5 text-sm font-medium ${
            value === o.key
              ? 'bg-indigo-600 text-white'
              : 'text-gray-700 hover:bg-gray-50'
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
}: {
  prompt: string
  typewriter: string
  loading: boolean
  onGenerate: () => void
}) {
  const display = loading || !prompt ? typewriter : prompt
  return (
    <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-indigo-900 uppercase tracking-wide">
          Đề bài
        </h2>
        <button
          onClick={onGenerate}
          disabled={loading}
          className="text-xs text-indigo-700 hover:text-indigo-900 underline disabled:opacity-50"
        >
          {prompt ? 'Đề khác' : 'Tạo đề'}
        </button>
      </div>
      <p className="text-indigo-900 whitespace-pre-line min-h-[3rem]">
        {display || 'Chưa có đề. Bấm "Tạo đề" để bắt đầu.'}
      </p>
    </div>
  )
}

export default function WritingPage() {
  const [taskType, setTaskType] = useState<TaskType>('task2')
  const [prompt, setPrompt] = useState('')
  const [typewriter, setTypewriter] = useState('')
  const [promptLoading, setPromptLoading] = useState(false)

  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [now, setNow] = useState<number>(Date.now())
  const [submission, setSubmission] = useState<WritingSubmission | null>(null)
  const [targetBand, setTargetBand] = useState<number>(7.0)

  const typeIntervalRef = useRef<number | null>(null)

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setTargetBand(p.target_band))
      .catch(() => {})
  }, [])

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
    setPromptLoading(true)
    setError(null)
    setPrompt('')
    setTypewriter('')
    try {
      const res = await apiFetch<{ prompt: string }>('/api/v1/writing/prompt', {
        method: 'POST',
        body: JSON.stringify({ task_type: taskType }),
      })
      if (typeIntervalRef.current) window.clearInterval(typeIntervalRef.current)
      let i = 0
      typeIntervalRef.current = window.setInterval(() => {
        i += 2
        setTypewriter(res.prompt.slice(0, i))
        if (i >= res.prompt.length) {
          window.clearInterval(typeIntervalRef.current!)
          typeIntervalRef.current = null
          setPrompt(res.prompt)
        }
      }, 15)
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
      const res = await apiFetch<WritingSubmission>('/api/v1/writing/submit', {
        method: 'POST',
        body: JSON.stringify({ text, task_type: taskType, prompt }),
      })
      setSubmission(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (submission) {
    return (
      <div className="max-w-3xl mx-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">
            ← Trang chủ
          </Link>
          <button
            onClick={() => {
              setSubmission(null)
              setText('')
              setPrompt('')
              setTypewriter('')
              setStartedAt(null)
            }}
            className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
          >
            Viết bài mới
          </button>
        </div>
        <ScorePanel submission={submission} targetBand={targetBand} />
        <VietnameseSummary summary={submission.summary_vi} />
        <AnnotatedEssay submission={submission} />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">
          ← Trang chủ
        </Link>
        <div className="flex items-center gap-3 text-sm text-gray-600">
          <span className="font-mono">{formatDuration(elapsed)}</span>
          <span>
            <span className={wordCount < MIN_WORDS ? 'text-red-600' : 'text-green-600'}>
              {wordCount}
            </span>{' '}
            từ
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <TaskSelector value={taskType} onChange={setTaskType} disabled={!!startedAt} />
      </div>

      <PromptCard
        prompt={prompt}
        typewriter={typewriter}
        loading={promptLoading}
        onGenerate={generatePrompt}
      />

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          if (!startedAt && e.target.value.length > 0) setStartedAt(Date.now())
        }}
        placeholder="Bắt đầu viết tại đây..."
        className="w-full min-h-[360px] p-4 bg-white rounded-xl border border-gray-200 focus:border-indigo-400 focus:outline-none text-gray-900 leading-relaxed"
      />

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">
          Tối thiểu {MIN_WORDS} từ để nộp bài.
        </p>
        <button
          onClick={submit}
          disabled={!canSubmit}
          className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? 'Đang chấm...' : 'Nộp bài'}
        </button>
      </div>
    </div>
  )
}
