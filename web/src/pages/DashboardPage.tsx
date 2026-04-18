import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { DailyPlan, greetingFor } from '../lib/plan'
import Icon from '../components/Icon'
import LinkTelegramCard from '../components/LinkTelegramCard'
import PlanTaskCard from '../components/PlanTaskCard'
import ProgressRing from '../components/ProgressRing'

interface UserProfile {
  id: string
  name: string
  email: string | null
  target_band: number
  topics: string[]
  streak: number
  total_words: number
}

function isWebPlaceholder(profile: UserProfile): boolean {
  return profile.id.startsWith('web_')
}

async function getOrCreateProfile(): Promise<UserProfile> {
  try {
    return await apiFetch<UserProfile>('/api/v1/me')
  } catch {
    return await apiFetch<UserProfile>('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify({
        name: 'IELTS Learner',
        target_band: 7.0,
        topics: ['education', 'environment', 'technology'],
      }),
    })
  }
}

export default function DashboardPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [plan, setPlan] = useState<DailyPlan | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = useCallback(() => {
    getOrCreateProfile()
      .then(setProfile)
      .catch((e) => setError(e.message))
  }, [])

  const loadPlan = useCallback(() => {
    apiFetch<DailyPlan>('/api/v1/plan/today')
      .then(setPlan)
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    loadProfile()
    loadPlan()
  }, [loadProfile, loadPlan])

  const toggle = async (activityId: string) => {
    if (busyId) return
    setBusyId(activityId)
    try {
      const updated = await apiFetch<DailyPlan>(
        `/api/v1/plan/today/complete/${encodeURIComponent(activityId)}`,
        { method: 'POST' },
      )
      setPlan(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const greeting = greetingFor(new Date())
  const allDone =
    plan && plan.activities.length > 0 &&
    plan.completed_count === plan.activities.length

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {profile ? (
        <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl p-5 text-white shadow-md">
          <p className="text-sm opacity-90">{greeting},</p>
          <p className="text-2xl font-bold">{profile.name}!</p>
          <div className="mt-3 flex items-center gap-4 text-sm">
            <div>
              <p className="opacity-80 text-xs uppercase tracking-wide">Band mục tiêu</p>
              <p className="text-xl font-semibold">{profile.target_band}</p>
            </div>
            <div>
              <p className="opacity-80 text-xs uppercase tracking-wide">Streak</p>
              <p className="text-xl font-semibold inline-flex items-center gap-1">
                <Icon name="Flame" size="md" variant="accent" label="Streak" />
                {profile.streak}
              </p>
            </div>
            <div>
              <p className="opacity-80 text-xs uppercase tracking-wide">Từ đã học</p>
              <p className="text-xl font-semibold">{profile.total_words}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="h-28 bg-gray-100 rounded-2xl animate-pulse" />
      )}

      {plan && plan.days_until_exam !== null && plan.days_until_exam >= 0 && (
        <div
          className={`rounded-xl p-3 text-sm font-medium border ${
            plan.exam_urgent
              ? 'bg-red-50 border-red-200 text-red-800'
              : 'bg-amber-50 border-amber-200 text-amber-800'
          }`}
        >
          <span className="inline-flex items-center gap-2">
            <Icon name="Hourglass" size="md" variant={plan.exam_urgent ? 'danger' : 'warning'} />
            Còn {plan.days_until_exam} ngày nữa đến IELTS
            {plan.exam_urgent && ' — tăng cường luyện tập!'}
          </span>
        </div>
      )}

      {plan && (
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-semibold text-gray-900">Kế hoạch hôm nay</h2>
              <p className="text-xs text-gray-500">
                {plan.total_minutes} phút · tối đa {plan.cap_minutes} phút
              </p>
            </div>
            <ProgressRing
              completed={plan.completed_count}
              total={plan.activities.length}
            />
          </div>

          {allDone ? (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
              <Icon name="PartyPopper" size="xl" variant="success" className="mx-auto" label="Hoàn thành" />
              <p className="font-semibold text-green-800 mt-1">
                Hoàn thành toàn bộ kế hoạch hôm nay!
              </p>
              <p className="text-xs text-green-700 mt-1">
                Mai quay lại để tiếp tục streak nhé.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {plan.activities.map((a) => (
                <PlanTaskCard
                  key={a.id}
                  activity={a}
                  onToggle={toggle}
                  busy={busyId === a.id}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {profile && isWebPlaceholder(profile) && (
        <LinkTelegramCard onLinked={loadProfile} />
      )}

    </div>
  )
}
