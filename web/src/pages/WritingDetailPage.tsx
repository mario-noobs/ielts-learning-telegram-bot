import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import {
  AnnotatedEssay,
  ScorePanel,
  VietnameseSummary,
} from '../components/WritingFeedback'
import WritingDiff from '../components/WritingDiff'
import { WritingSubmission } from '../lib/writing'

interface UserProfile {
  target_band: number
}

export default function WritingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<WritingSubmission | null>(null)
  const [original, setOriginal] = useState<WritingSubmission | null>(null)
  const [targetBand, setTargetBand] = useState<number>(7.0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setTargetBand(p.target_band))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!id) return
    setData(null)
    setOriginal(null)
    setError(null)
    apiFetch<WritingSubmission>(`/api/v1/writing/${id}`)
      .then((res) => {
        setData(res)
        if (res.original_id) {
          return apiFetch<WritingSubmission>(`/api/v1/writing/${res.original_id}`)
            .then(setOriginal)
            .catch(() => {})
        }
      })
      .catch((e) => setError(e.message))
  }, [id])

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-4">
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg text-danger">
          {error}
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="max-w-3xl mx-auto p-4 animate-pulse space-y-3">
        <div className="h-8 bg-border rounded w-1/3" />
        <div className="h-32 bg-border rounded" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/write/history" className="text-sm text-muted-fg hover:text-fg">
          Lịch sử bài viết
        </Link>
        <button
          onClick={() => navigate(`/write?reviseOf=${data.id}`)}
          className="px-4 py-1.5 bg-primary text-primary-fg text-sm rounded-lg font-medium hover:bg-primary-hover"
        >
          Viết lại
        </button>
      </div>

      {data.delta_band !== null && data.delta_band !== undefined && (
        <div
          className={`rounded-xl p-4 ${
            data.delta_band >= 0
              ? 'bg-success/10 border-l-4 border-success'
              : 'bg-danger/10 border-l-4 border-danger'
          }`}
        >
          <p className="font-medium text-fg">
            Thay đổi so với bản gốc:{' '}
            <span className={data.delta_band >= 0 ? 'text-success' : 'text-danger'}>
              {data.delta_band > 0 ? '+' : ''}
              {data.delta_band.toFixed(1)} band
            </span>
          </p>
        </div>
      )}

      <ScorePanel submission={data} targetBand={targetBand} />
      <VietnameseSummary summary={data.summary_vi} />
      {original && <WritingDiff original={original.text} revised={data.text} />}
      <AnnotatedEssay submission={data} />
    </div>
  )
}
