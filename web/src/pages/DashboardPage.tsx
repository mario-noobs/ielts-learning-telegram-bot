import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../lib/api'
import { DailyPlan } from '../lib/plan'
import type { ProgressResponse } from '../lib/progress'
import EmptyState from '../components/EmptyState'
import ErrorBanner from '../components/ErrorBanner'
import Icon from '../components/Icon'
import LinkTelegramCard from '../components/LinkTelegramCard'
import PlanTaskCard from '../components/PlanTaskCard'
import ProgressRing from '../components/ProgressRing'
import DashboardGreeting from './dashboard/DashboardGreeting'
import QuickActions from './dashboard/QuickActions'
import PersonalizationCTA from './dashboard/PersonalizationCTA'
import ReadinessStrip from './dashboard/ReadinessStrip'
import RecentContent from './dashboard/RecentContent'
import ProfilePanel from './dashboard/ProfilePanel'

interface UserProfile {
  id: string
  name: string
  email: string | null
  target_band: number
  exam_date: string | null
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
  const { t } = useTranslation('dashboard')
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [plan, setPlan] = useState<DailyPlan | null>(null)
  const [progress, setProgress] = useState<ProgressResponse | null>(null)
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

  const loadProgress = useCallback(() => {
    apiFetch<ProgressResponse>('/api/v1/progress')
      .then(setProgress)
      .catch(() => setProgress(null))
  }, [])

  useEffect(() => {
    loadProfile()
    loadPlan()
    loadProgress()
  }, [loadProfile, loadPlan, loadProgress])

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

  const allDone =
    plan && plan.activities.length > 0 &&
    plan.completed_count === plan.activities.length

  const showPersonalizationCta =
    !!profile && (!profile.target_band || !profile.exam_date)
  const ctaFocusField: 'target-band' | 'exam-date' =
    profile && !profile.target_band ? 'target-band' : 'exam-date'

  return (
    <div className="mx-auto max-w-6xl p-4 md:p-6">
      <ErrorBanner
        error={error}
        onRetry={() => {
          setError(null)
          loadProfile()
          loadPlan()
          loadProgress()
        }}
      />

      {!profile ? (
        <DashboardSkeleton />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main column */}
          <div className="flex flex-col gap-6 lg:col-span-2">
            <DashboardGreeting name={profile.name} />

            <QuickActions />

            {showPersonalizationCta && (
              <PersonalizationCTA focusField={ctaFocusField} />
            )}

            {plan && plan.days_until_exam !== null && plan.days_until_exam >= 0 && (
              <div
                className={`rounded-xl border p-3 text-sm font-medium ${
                  plan.exam_urgent
                    ? 'bg-danger/10 border-danger/30 text-danger'
                    : 'bg-warning/10 border-warning/30 text-warning'
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  <Icon
                    name="Hourglass"
                    size="md"
                    variant={plan.exam_urgent ? 'danger' : 'warning'}
                  />
                  {t('examCountdown.days', { count: plan.days_until_exam })}
                  {plan.exam_urgent && t('examCountdown.urgent')}
                </span>
              </div>
            )}

            {plan && (
              <section
                aria-labelledby="todays-plan-heading"
                className="rounded-2xl border border-border bg-surface-raised p-4"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h2
                      id="todays-plan-heading"
                      className="font-semibold text-fg"
                    >
                      {t('todaysPlan.heading')}
                    </h2>
                    <p className="text-xs text-muted-fg">
                      {t('todaysPlan.subline', {
                        total: plan.total_minutes,
                        cap: plan.cap_minutes,
                      })}
                    </p>
                  </div>
                  <ProgressRing
                    completed={plan.completed_count}
                    total={plan.activities.length}
                  />
                </div>

                {allDone ? (
                  <EmptyState
                    illustration="plan-complete"
                    title={t('todaysPlan.allDone.title')}
                    description={t('todaysPlan.allDone.description')}
                    variant="celebration"
                    primaryAction={{
                      label: t('todaysPlan.allDone.cta'),
                      to: '/progress',
                    }}
                  />
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
              </section>
            )}

            <ReadinessStrip progress={progress} />

            {/* Profile panel stacks between readiness and recent on <lg per AC7 */}
            <div className="lg:hidden">
              <ProfilePanel profile={profile} progress={progress} />
            </div>

            <RecentContent />

            {isWebPlaceholder(profile) && (
              <LinkTelegramCard onLinked={loadProfile} />
            )}
          </div>

          {/* Right column — desktop only */}
          <div className="hidden lg:block">
            <ProfilePanel profile={profile} progress={progress} />
          </div>
        </div>
      )}
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="flex flex-col gap-6 lg:col-span-2">
        <div className="h-32 animate-pulse rounded-2xl bg-surface" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="h-24 animate-pulse rounded-2xl bg-surface" />
          <div className="h-24 animate-pulse rounded-2xl bg-surface" />
        </div>
        <div className="h-40 animate-pulse rounded-2xl bg-surface" />
      </div>
      <div className="hidden lg:flex lg:flex-col lg:gap-4">
        <div className="h-28 animate-pulse rounded-2xl bg-surface" />
        <div className="h-28 animate-pulse rounded-2xl bg-surface" />
        <div className="h-40 animate-pulse rounded-2xl bg-surface" />
      </div>
    </div>
  )
}
