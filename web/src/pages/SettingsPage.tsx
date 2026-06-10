import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon, { IconName } from '../components/Icon'
import TelegramIcon from '../components/icons/Telegram'
import PlanBadge from '../components/PlanBadge'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { ThemePref, useTheme } from '../lib/theme'


/**
 * 5-tab Settings page (US-M14.1):
 *   Profile · Goals · Practice · Plan · Privacy
 *
 * Theme + locale are intentionally NOT in their own tab here — they
 * live in the sidebar bottom group (touchpoints, set-once behaviour).
 * If a user lands on /settings#<tab>, that tab is preselected.
 */

const TABS = ['profile', 'goals', 'practice', 'plan', 'privacy'] as const
type TabKey = (typeof TABS)[number]

// Tab → icon mapping. Icons make the tab list scannable on mobile
// where the labels truncate, and pair well with the active-tab
// underline indicator below.
const TAB_ICONS: Record<TabKey, IconName> = {
  profile: 'User',
  goals: 'Target',
  practice: 'PenLine',
  plan: 'Sparkles',
  privacy: 'ShieldCheck',
}

// Deep-link fragments coming from outside (Dashboard PersonalizationCTA,
// emails, blog links) point at a *field*, not a tab. We resolve those
// to the tab that owns the field + the input id to focus on mount.
// Add new entries here when surfacing a field as a deep-link target.
const FRAGMENT_TO_FOCUS: Record<string, { tab: TabKey; elementId: string }> = {
  'exam-date': { tab: 'goals', elementId: 'goals-exam' },
  'target-band': { tab: 'goals', elementId: 'goals-band' },
  'weekly-goal': { tab: 'goals', elementId: 'goals-weekly' },
  'daily-time': { tab: 'practice', elementId: 'practice-time' },
  'daily-words': { tab: 'practice', elementId: 'practice-words' },
}

const COMMON_TZ = [
  'Asia/Ho_Chi_Minh',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'UTC',
] as const

const IELTS_TOPICS = [
  'education', 'environment', 'technology', 'health',
  'society', 'economy', 'government', 'media',
  'science', 'travel', 'food', 'arts',
] as const

interface UserProfile {
  id: string
  name: string
  email: string | null
  target_band: number
  topics: string[]
  streak: number
  exam_date: string | null
  weekly_goal_minutes: number
  daily_time: string | null
  timezone: string | null
  daily_words_count: number
  dismissed_onboarding: boolean
  plan: string
  preferred_locale: 'en' | 'vi' | null
}

interface StudyWeek {
  minutes_actual: number
  minutes_goal: number
  by_feature: { feature: string; count: number; minutes: number }[]
  week_start: string
}

type ExamPhase =
  | 'past'
  | 'examDay'
  | 'examWeek'
  | 'final'
  | 'sharpen'
  | 'build'
  | 'foundation'

interface PhaseStyle {
  key: ExamPhase
  cardCls: string
  chipCls: string
}

function phaseFromDays(days: number): PhaseStyle {
  if (days < 0) {
    return {
      key: 'past',
      cardCls: 'border-border bg-surface',
      chipCls: 'bg-muted-fg/10 text-muted-fg',
    }
  }
  if (days === 0) {
    return {
      key: 'examDay',
      cardCls: 'border-primary/40 bg-primary/5',
      chipCls: 'bg-primary/15 text-primary',
    }
  }
  if (days <= 6) {
    return {
      key: 'examWeek',
      cardCls: 'border-danger/30 bg-danger/5',
      chipCls: 'bg-danger/15 text-danger',
    }
  }
  if (days <= 29) {
    return {
      key: 'final',
      cardCls: 'border-warning/30 bg-warning/5',
      chipCls: 'bg-warning/15 text-warning',
    }
  }
  if (days <= 89) {
    return {
      key: 'sharpen',
      cardCls: 'border-warning/20 bg-warning/5',
      chipCls: 'bg-warning/10 text-warning',
    }
  }
  if (days <= 179) {
    return {
      key: 'build',
      cardCls: 'border-primary/20 bg-primary/5',
      chipCls: 'bg-primary/10 text-primary',
    }
  }
  return {
    key: 'foundation',
    cardCls: 'border-success/20 bg-success/5',
    chipCls: 'bg-success/10 text-success',
  }
}

interface ExamCountdownCardProps {
  examDate: string
  weeklyGoalMinutes: number
  onClear: () => void
  locale: string
}

function ExamCountdownCard({
  examDate,
  weeklyGoalMinutes,
  onClear,
  locale,
}: ExamCountdownCardProps) {
  const { t } = useTranslation('settings')

  const parsed = new Date(examDate + 'T00:00:00')
  if (Number.isNaN(parsed.getTime())) return null

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const msPerDay = 86_400_000
  const days = Math.round((parsed.getTime() - today.getTime()) / msPerDay)

  const phase = phaseFromDays(days)
  const formatted = new Intl.DateTimeFormat(
    locale === 'vi' ? 'vi-VN' : 'en-US',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' },
  ).format(parsed)

  // Breakdown is only meaningful for future dates.
  const weeks = days > 0 ? Math.round(days / 7) : 0
  const months = days > 0 ? Math.max(1, Math.round(days / 30)) : 0
  const studyHours =
    days > 0 ? Math.round((weeks * weeklyGoalMinutes) / 60) : 0

  return (
    <div className={`rounded-lg border p-4 space-y-3 ${phase.cardCls}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-muted-fg leading-tight">{formatted}</p>
        <span
          className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${phase.chipCls}`}
        >
          {t(`examDate.phase.${phase.key}`)}
        </span>
      </div>

      {days >= 0 ? (
        <div className="flex items-baseline gap-4">
          <div>
            <div className="text-3xl font-bold text-fg leading-none">{days}</div>
            <div className="text-xs text-muted-fg mt-1">
              {t('examDate.daysUnit', { count: days })}
            </div>
          </div>
          {days > 0 && (
            <div className="text-xs text-muted-fg space-y-1">
              <div>
                {t('examDate.weeksMonths', { weeks, months })}
              </div>
              {studyHours > 0 && (
                <div>
                  {t('examDate.studyHoursProjection', {
                    hours: studyHours,
                    min: weeklyGoalMinutes,
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      ) : null}

      <p className="text-sm text-fg">
        {t(`examDate.phase.${phase.key}Copy`)}
      </p>

      <button
        type="button"
        onClick={onClear}
        className="text-xs text-muted-fg hover:text-fg underline"
      >
        {t('examDate.clear')}
      </button>
    </div>
  )
}

function WeeklyProgress({ data }: { data: StudyWeek }) {
  const { t } = useTranslation('settings')
  const pct = data.minutes_goal > 0
    ? Math.min(100, Math.round((data.minutes_actual / data.minutes_goal) * 100))
    : 0

  // Pace check: how many minutes the user *should* have logged by now
  // if they were on track (linear daily pace, Mon=day 1).
  const now = new Date()
  const day = now.getUTCDay() || 7  // Sun=0 → 7
  const expected = (data.minutes_goal / 7) * day
  const onTrack = data.minutes_actual >= expected

  // Bar color tracks distance from goal — clearer than mixing the
  // pct-bucket and the on-track signal.
  const barCls = pct >= 80
    ? 'bg-success'
    : pct >= 50
    ? 'bg-warning'
    : 'bg-muted-fg/40'

  const breakdown = data.by_feature.filter((f) => f.minutes > 0)

  return (
    <div className="rounded-lg border border-border p-3 space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-fg">
          {t('weeklyProgress.heading')}
        </h3>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            onTrack
              ? 'bg-success/10 text-success'
              : 'bg-warning/10 text-warning'
          }`}
        >
          {onTrack
            ? t('weeklyProgress.onTrack')
            : t('weeklyProgress.behind')}
        </span>
      </div>
      <div>
        <div className="flex justify-between text-xs text-muted-fg mb-1">
          <span>
            {t('weeklyProgress.minutesOf', {
              actual: data.minutes_actual,
              goal: data.minutes_goal,
            })}
          </span>
          <span>{pct}%</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 rounded-full bg-surface overflow-hidden"
        >
          <div
            className={`h-full rounded-full ${barCls} transition-all duration-base`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      {breakdown.length > 0 && (
        <details className="text-xs text-muted-fg">
          <summary className="cursor-pointer hover:text-fg">
            {t('weeklyProgress.perFeature')}
          </summary>
          <ul className="mt-2 space-y-1">
            {breakdown.map((f) => (
              <li key={f.feature} className="flex justify-between">
                <span>{t(`weeklyProgress.feature.${f.feature}`)}</span>
                <span>
                  {t('weeklyProgress.featureLine', {
                    count: f.count,
                    minutes: f.minutes,
                  })}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function ThemeToggle() {
  const { t } = useTranslation('settings')
  const { pref, setPref } = useTheme()
  const options: { value: ThemePref; label: string }[] = [
    { value: 'system', label: t('theme.system') },
    { value: 'light', label: t('theme.light') },
    { value: 'dark', label: t('theme.dark') },
  ]
  return (
    <div>
      <label id="theme-label" className="text-sm font-semibold text-fg block mb-1">
        {t('theme.label')}
      </label>
      <div
        role="radiogroup"
        aria-labelledby="theme-label"
        className="inline-flex rounded-lg border border-border bg-surface-raised overflow-hidden"
      >
        {options.map((o) => (
          <button
            key={o.value}
            role="radio"
            aria-checked={pref === o.value}
            onClick={() => setPref(o.value)}
            className={`px-4 py-2 min-h-[44px] text-sm font-medium transition-colors duration-base ${
              pref === o.value
                ? 'bg-primary text-primary-fg'
                : 'text-fg hover:bg-surface'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { t, i18n } = useTranslation(['settings', 'common', 'link', 'usage', 'vocab'])
  const { logout } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)

  // Field-level deep-link (e.g. /settings#exam-date) routes the user
  // to the tab that owns the field; we keep `pendingFocusId` so an
  // effect can focus the input after the tab content actually mounts.
  const initialHash =
    typeof window !== 'undefined'
      ? window.location.hash.replace('#', '')
      : ''
  const fieldRoute = FRAGMENT_TO_FOCUS[initialHash]
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (fieldRoute) return fieldRoute.tab
    return TABS.includes(initialHash as TabKey) ? (initialHash as TabKey) : 'profile'
  })
  const [pendingFocusId, setPendingFocusId] = useState<string | null>(
    fieldRoute ? fieldRoute.elementId : null,
  )

  // Profile-tab state
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('Asia/Ho_Chi_Minh')

  // Goals-tab state
  const [targetBand, setTargetBand] = useState(7.0)
  const [examDate, setExamDate] = useState('')
  const [weeklyGoal, setWeeklyGoal] = useState(150)
  const [studyWeek, setStudyWeek] = useState<StudyWeek | null>(null)

  // Practice-tab state
  const [topics, setTopics] = useState<string[]>([])
  const [dailyTime, setDailyTime] = useState('')
  const [dailyWordsCount, setDailyWordsCount] = useState(5)

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => {
        setProfile(p)
        setName(p.name ?? '')
        setTimezone(p.timezone || 'Asia/Ho_Chi_Minh')
        setTargetBand(p.target_band ?? 7.0)
        setExamDate(p.exam_date ?? '')
        setWeeklyGoal(p.weekly_goal_minutes ?? 150)
        // Defensive: legacy data may have topics stored as a string;
        // coerce non-arrays to [] so `topics.length` reflects actual chips.
        setTopics(Array.isArray(p.topics) ? p.topics : [])
        setDailyTime(p.daily_time ?? '')
        setDailyWordsCount(
          typeof p.daily_words_count === 'number' ? p.daily_words_count : 5,
        )
      })
      .catch((e) => setError(localizeError(e)))
  }, [])

  // Fetch the weekly study summary lazily when Goals tab is opened.
  // Re-fetches on tab focus so a cross-device session reflects new
  // completions without a hard reload.
  useEffect(() => {
    if (activeTab !== 'goals') return
    const load = () => {
      apiFetch<StudyWeek>('/api/v1/me/study-week')
        .then(setStudyWeek)
        .catch(() => {/* widget hides; not worth surfacing as error */})
    }
    load()
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [activeTab])

  // Persist active tab to hash for deep-linking.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const newHash = `#${activeTab}`
    if (window.location.hash !== newHash) {
      window.history.replaceState(null, '', newHash)
    }
  }, [activeTab])

  // After a field-level deep-link routes us to the right tab, scroll
  // the target input into view and focus it. Waits for the profile
  // load + tab content to mount via requestAnimationFrame so the node
  // is in the DOM. One-shot — clears `pendingFocusId` after firing.
  useEffect(() => {
    if (!pendingFocusId || !profile) return
    const id = pendingFocusId
    const raf = requestAnimationFrame(() => {
      const el = document.getElementById(id)
      if (el) {
        // jsdom doesn't implement scrollIntoView; guard so unit tests
        // exercising the deep-link path don't blow up.
        if (typeof el.scrollIntoView === 'function') {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
        if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement) {
          el.focus({ preventScroll: true })
        }
      }
      setPendingFocusId(null)
    })
    return () => cancelAnimationFrame(raf)
  }, [pendingFocusId, profile])

  // Auto-clear "saved" toast after 3s.
  useEffect(() => {
    if (!saved) return
    const to = setTimeout(() => setSaved(false), 3000)
    return () => clearTimeout(to)
  }, [saved])

  const save = async (patch: Record<string, unknown>) => {
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      const updated = await apiFetch<UserProfile>('/api/v1/me', {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setProfile(updated)
      setSaved(true)
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSaving(false)
    }
  }

  const toggleTopic = async (slug: string) => {
    const next = topics.includes(slug)
      ? topics.filter((x) => x !== slug)
      : topics.length < 5 ? [...topics, slug] : topics
    if (next === topics) return
    setTopics(next)
    await save({ topics: next })
  }

  const isLinked = !!profile && profile.id && !profile.id.startsWith('web_')

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-fg">{t('heading')}</h1>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
          {error}
        </div>
      )}
      {saved && (
        <div
          role="status"
          aria-live="polite"
          className="bg-success/10 border-l-4 border-success p-3 rounded text-sm text-success"
        >
          {t('savedToast')}
        </div>
      )}

      {/* Tabs */}
      <div
        role="tablist"
        aria-label={t('tabs.ariaLabel')}
        className="flex gap-1 overflow-x-auto border-b border-border"
      >
        {TABS.map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={activeTab === key}
            aria-controls={`settings-tab-${key}`}
            onClick={() => setActiveTab(key)}
            className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors duration-fast ${
              activeTab === key
                ? 'text-primary border-primary'
                : 'text-muted-fg border-transparent hover:text-fg'
            }`}
          >
            <Icon name={TAB_ICONS[key]} size="sm" />
            {t(`tabs.${key}`)}
          </button>
        ))}
      </div>

      {!profile && <p className="text-muted-fg">{t('common:status.loading')}</p>}

      {profile && (
        <>
          {/* PROFILE TAB */}
          {activeTab === 'profile' && (
            <section
              id="settings-tab-profile"
              role="tabpanel"
              className="rounded-xl border border-border bg-surface-raised p-4 space-y-4"
            >
              <div>
                <label htmlFor="profile-name" className="text-sm font-semibold text-fg block mb-1">
                  {t('profile.name')}
                </label>
                <input
                  id="profile-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={60}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                />
              </div>
              <div>
                <label className="text-sm font-semibold text-fg block mb-1">
                  {t('profile.email')}
                </label>
                <input
                  type="email"
                  value={profile.email ?? ''}
                  readOnly
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-muted-fg cursor-not-allowed"
                />
              </div>
              <div>
                <label htmlFor="profile-tz" className="text-sm font-semibold text-fg block mb-1">
                  {t('profile.timezone')}
                </label>
                <select
                  id="profile-tz"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                >
                  {COMMON_TZ.map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => save({ name: name.trim(), timezone })}
                disabled={saving}
                className="w-full py-2 bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
              >
                {saving ? t('common:status.saving') : t('common:actions.save')}
              </button>
            </section>
          )}

          {/* GOALS TAB */}
          {activeTab === 'goals' && (
            <section
              id="settings-tab-goals"
              role="tabpanel"
              className="rounded-xl border border-border bg-surface-raised p-4 space-y-4"
            >
              {studyWeek && <WeeklyProgress data={studyWeek} />}
              <div>
                <label htmlFor="goals-band" className="text-sm font-semibold text-fg block mb-1">
                  {t('goals.targetBand')}: <span className="text-primary">{targetBand.toFixed(1)}</span>
                </label>
                <input
                  id="goals-band"
                  type="range"
                  min={4.0}
                  max={9.0}
                  step={0.5}
                  value={targetBand}
                  onChange={(e) => setTargetBand(Number(e.target.value))}
                  className="w-full"
                />
                <div className="mt-1 flex justify-between text-xs text-muted-fg">
                  <span>4.0</span>
                  <span>9.0</span>
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="goals-exam" className="text-sm font-semibold text-fg block">
                  {t('examDate.label')}
                </label>
                <input
                  id="goals-exam"
                  type="date"
                  value={examDate}
                  onChange={(e) => setExamDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                />
                {examDate ? (
                  <ExamCountdownCard
                    examDate={examDate}
                    weeklyGoalMinutes={weeklyGoal}
                    onClear={() => setExamDate('')}
                    locale={i18n.language}
                  />
                ) : (
                  <p className="text-xs text-muted-fg">
                    {t('examDate.unsetHint')}
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="goals-weekly" className="text-sm font-semibold text-fg block mb-1">
                  {t('weeklyGoal.label')}
                </label>
                <input
                  id="goals-weekly"
                  type="number"
                  min={30}
                  max={2000}
                  step={10}
                  value={weeklyGoal}
                  onChange={(e) => setWeeklyGoal(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                />
                <p className="text-xs text-muted-fg mt-1">
                  {t('weeklyGoal.dailyAverage', { count: Math.round(weeklyGoal / 7) })}
                </p>
              </div>
              <button
                onClick={() =>
                  save({
                    target_band: targetBand,
                    exam_date: examDate || '',
                    weekly_goal_minutes: weeklyGoal,
                  })
                }
                disabled={saving}
                className="w-full py-2 bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
              >
                {saving ? t('common:status.saving') : t('common:actions.save')}
              </button>
            </section>
          )}

          {/* PRACTICE TAB */}
          {activeTab === 'practice' && (
            <section
              id="settings-tab-practice"
              role="tabpanel"
              className="rounded-xl border border-border bg-surface-raised p-4 space-y-4"
            >
              <div className="flex items-center gap-2 text-xs">
                {isLinked ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-success">
                    <Icon name="Check" size="sm" variant="success" /> {t('practice.synced')}
                  </span>
                ) : (
                  <Link
                    to="/settings/link-telegram"
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-muted-fg hover:text-fg"
                  >
                    {t('practice.notLinked')}
                  </Link>
                )}
              </div>

              {/* US-#227 — entry point to /settings/groups. Only worth
                  showing when the user is linked to Telegram (otherwise
                  they have no groups). */}
              {isLinked && (
                <Link
                  to="/settings/groups"
                  className="block rounded-lg border border-border bg-surface p-3 hover:bg-surface-raised"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Icon name="Crown" size="md" variant="primary" />
                    </span>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-fg">
                        {t('practice.groupsLinkTitle')}
                      </p>
                      <p className="text-xs text-muted-fg mt-0.5">
                        {t('practice.groupsLinkDescription')}
                      </p>
                    </div>
                    <span aria-hidden className="text-muted-fg">→</span>
                  </div>
                </Link>
              )}

              <div>
                <label className="text-sm font-semibold text-fg block mb-1">
                  {t('practice.topics')}
                </label>
                <p className="text-xs text-muted-fg mb-2">{t('practice.topicsHint')}</p>
                <div className="flex flex-wrap gap-2">
                  {IELTS_TOPICS.map((slug) => {
                    const selected = topics.includes(slug)
                    const atLimit = !selected && topics.length >= 5
                    return (
                      <button
                        key={slug}
                        type="button"
                        onClick={() => toggleTopic(slug)}
                        disabled={atLimit || saving}
                        aria-pressed={selected}
                        className={[
                          'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
                          selected
                            ? 'bg-primary text-primary-fg'
                            : 'bg-surface border border-border text-muted-fg hover:border-primary/50 hover:text-fg disabled:opacity-40',
                        ].join(' ')}
                      >
                        {selected && <span aria-hidden>✓</span>}
                        {t(`vocab:topicNames.${slug}`, { defaultValue: slug })}
                      </button>
                    )
                  })}
                </div>
                <p className="text-xs text-muted-fg mt-2">
                  {topics.length}/5 {t('practice.topicsHint')}
                </p>
              </div>

              <div>
                <label htmlFor="practice-time" className="text-sm font-semibold text-fg block mb-1">
                  {t('practice.dailyTime')}
                </label>
                <input
                  id="practice-time"
                  type="time"
                  value={dailyTime}
                  onChange={(e) => setDailyTime(e.target.value)}
                  disabled={!isLinked}
                  className="px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                />
                {isLinked ? (
                  <p className="text-xs text-muted-fg mt-1">
                    {t('practice.dailyTimeHint', { tz: timezone })}
                  </p>
                ) : (
                  <Link
                    to="/settings/link-telegram"
                    className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-primary hover:underline"
                  >
                    {t('practice.reminderLinkCta')} →
                  </Link>
                )}
              </div>

              <div>
                <label htmlFor="practice-words" className="text-sm font-semibold text-fg block mb-1">
                  {t('practice.dailyWordsCount')}
                </label>
                <select
                  id="practice-words"
                  value={dailyWordsCount}
                  onChange={(e) => setDailyWordsCount(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                >
                  {[5, 10, 20, 30, 50].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-fg mt-1">
                  {t('practice.dailyWordsCountHint')}
                </p>
              </div>

              {/* topics chips auto-save on add/remove. The Save button
                  on this tab persists daily_time + daily_words_count. */}
              <button
                onClick={() =>
                  save({
                    daily_time: dailyTime || null,
                    daily_words_count: dailyWordsCount,
                  })
                }
                disabled={saving}
                className="w-full py-2 bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
              >
                {saving ? t('common:status.saving') : t('common:actions.save')}
              </button>
            </section>
          )}

          {/* PLAN TAB */}
          {activeTab === 'plan' && (
            <section
              id="settings-tab-plan"
              role="tabpanel"
              className="rounded-xl border border-border bg-surface-raised p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-fg">{t('plan.heading')}</h2>
                  <p className="text-sm text-muted-fg mt-1">{t('plan.subtitle')}</p>
                </div>
                <PlanBadge plan={profile.plan} hideUpgrade />
              </div>
              <Link
                to="/settings/usage"
                className="block rounded-lg border border-border bg-surface p-3 hover:bg-surface-raised"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Icon name="Zap" size="md" variant="primary" />
                  </span>
                  <span className="flex-1 text-sm text-fg">
                    {t('usage:page.settingsLink')}
                  </span>
                  <span aria-hidden className="text-muted-fg">→</span>
                </div>
              </Link>
              {profile.plan === 'free' && (
                <Link
                  to="/pricing"
                  className="block w-full text-center py-2 rounded-lg bg-primary text-primary-fg font-medium hover:bg-primary-hover"
                >
                  {t('plan.upgrade')}
                </Link>
              )}
              {/* Theme + locale pinned at the bottom of Plan tab as
                  general-purpose preferences (sidebar already has the
                  primary controls for these). */}
              <div className="border-t border-border pt-4">
                <ThemeToggle />
              </div>
            </section>
          )}

          {/* PRIVACY TAB */}
          {activeTab === 'privacy' && (
            <section
              id="settings-tab-privacy"
              role="tabpanel"
              className="rounded-xl border border-border bg-surface-raised p-4 space-y-2"
            >
              <div className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Icon name="Users" size="md" variant="primary" />
                  </span>
                  <div>
                    <p className="font-medium text-fg">{t('privacy.team.heading')}</p>
                    <p className="mt-1 text-xs text-muted-fg">
                      {t('privacy.team.description')}
                    </p>
                    <p className="mt-2 text-xs text-muted-fg">
                      {t('privacy.team.privateDetails')}
                    </p>
                  </div>
                </div>
              </div>
              <Link
                to="/settings/link-telegram"
                className="block rounded-lg border border-border bg-surface p-3 hover:bg-surface-raised"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <TelegramIcon size={20} />
                  </span>
                  <div className="flex-1">
                    <p className="font-medium text-fg">{t('link:settings.heading')}</p>
                    <p className="text-xs text-muted-fg mt-0.5">
                      {t('link:settings.linked.description')}
                    </p>
                  </div>
                  <span aria-hidden className="text-muted-fg">→</span>
                </div>
              </Link>
              <p className="text-xs text-muted-fg pt-2">{t('privacy.deferNote')}</p>
            </section>
          )}
        </>
      )}

      {/* Session action — always visible, especially useful on mobile where
          the sidebar sign-out button is not rendered. */}
      <div className="rounded-xl border border-danger/20 bg-danger/5 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
              <Icon name="LogOut" size="md" variant="danger" />
            </span>
            <div>
              <p className="text-sm font-semibold text-fg">
                {t('session.heading', {
                  defaultValue: 'Signed in on this device',
                })}
              </p>
              <p className="mt-1 text-sm text-muted-fg">
                {t('session.description', {
                  defaultValue: 'Sign out when you are done, especially on a shared computer.',
                })}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="inline-flex min-h-10 items-center justify-center rounded-lg border border-danger/30 bg-surface-raised px-4 text-sm font-semibold text-danger hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger focus-visible:ring-offset-2"
          >
            {t('common:nav.signOut')}
          </button>
        </div>
      </div>
    </div>
  )
}
