import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import BandRing from '../components/BandRing'
import BandTrendChart from '../components/BandTrendChart'
import CoachingPanel from '../components/CoachingPanel'
import ErrorBanner from '../components/ErrorBanner'
import SkillBandCard from '../components/SkillBandCard'
import {
  deltaFrom,
  ProgressResponse,
  timeToTarget,
} from '../lib/progress'

export default function ProgressPage() {
  const [data, setData] = useState<ProgressResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<ProgressResponse>('/api/v1/progress')
      .then(setData)
      .catch((e) => setError((e as Error).message))
  }, [])

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-4">
        <ErrorBanner error={error} onRetry={() => window.location.reload()} />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-3">
        <div className="h-7 bg-surface rounded w-40 animate-pulse" />
        <div className="h-56 bg-surface rounded-xl animate-pulse" />
        <div className="grid grid-cols-2 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-surface rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const { snapshot, trend, predictions } = data
  const target = snapshot.target_band
  const eta = timeToTarget(snapshot.overall_band, target, trend)

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-5">
      <div className="flex items-center justify-end">
        <Link
          to="/settings"
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          Đổi mục tiêu
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-fg">Band Progress</h1>
        <p className="text-sm text-muted-fg">
          Cập nhật từ bài nghe, viết, và từ vựng của bạn.
        </p>
      </div>

      <div className="bg-surface-raised rounded-2xl border border-border p-5 flex flex-col sm:flex-row items-center gap-4">
        <BandRing band={snapshot.overall_band} target={target} />
        <div className="flex-1 text-center sm:text-left space-y-1">
          <p className="text-sm text-muted-fg">
            Cách mục tiêu {(target - snapshot.overall_band).toFixed(1)} band
          </p>
          {eta && <p className="text-sm text-primary font-medium">{eta}</p>}
          {predictions.length > 0 && (
            <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
              {predictions.map((p) => (
                <div
                  key={p.days_ahead}
                  className="bg-surface rounded-lg p-2 border border-border"
                >
                  <p className="text-muted-fg">+{p.days_ahead} ngày</p>
                  <p className="text-base font-semibold text-fg">
                    {p.projected_band.toFixed(1)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <SkillBandCard
          iconName="BookOpen"
          label="Vocabulary"
          band={snapshot.skills.vocabulary.band}
          target={target}
          delta={deltaFrom(trend, 'vocabulary_band')}
          subline={`${snapshot.skills.vocabulary.total_words} từ · ${snapshot.skills.vocabulary.mastered_count} đã thuộc`}
        />
        <SkillBandCard
          iconName="PenLine"
          label="Writing"
          band={snapshot.skills.writing.band}
          target={target}
          delta={deltaFrom(trend, 'writing_band')}
          subline={
            snapshot.skills.writing.sample_size > 0
              ? `Trung bình ${snapshot.skills.writing.sample_size} bài gần nhất`
              : 'Chưa có bài viết nào'
          }
        />
        <SkillBandCard
          iconName="Headphones"
          label="Listening"
          band={snapshot.skills.listening.band}
          target={target}
          delta={deltaFrom(trend, 'listening_band')}
          subline={
            snapshot.skills.listening.sample_size > 0
              ? `${snapshot.skills.listening.sample_size} bài đã chấm`
              : 'Chưa có bài nghe nào'
          }
        />
        <SkillBandCard
          iconName="Mic"
          label="Speaking"
          band={0}
          target={target}
          placeholder
        />
      </div>

      <div>
        <h2 className="text-sm font-semibold text-fg mb-2">Xu hướng 30 ngày</h2>
        <BandTrendChart trend={trend} target={target} />
      </div>

      <CoachingPanel />
    </div>
  )
}
