import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import PlanBadge from '../components/PlanBadge'
import { apiFetch } from '../lib/api'
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
  plan: string
  preferred_locale: 'en' | 'vi' | null
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
  const { t } = useTranslation(['settings', 'common', 'link', 'usage'])
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    const hash = (typeof window !== 'undefined'
      ? window.location.hash.replace('#', '')
      : '') as TabKey
    return TABS.includes(hash) ? hash : 'profile'
  })

  // Profile-tab state
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('Asia/Ho_Chi_Minh')

  // Goals-tab state
  const [targetBand, setTargetBand] = useState(7.0)
  const [examDate, setExamDate] = useState('')
  const [weeklyGoal, setWeeklyGoal] = useState(150)

  // Practice-tab state
  const [topics, setTopics] = useState<string[]>([])
  const [topicDraft, setTopicDraft] = useState('')
  const [dailyTime, setDailyTime] = useState('')

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
      })
      .catch((e) => setError((e as Error).message))
  }, [])

  // Persist active tab to hash for deep-linking.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const newHash = `#${activeTab}`
    if (window.location.hash !== newHash) {
      window.history.replaceState(null, '', newHash)
    }
  }, [activeTab])

  // Auto-clear "saved" toast after 3s.
  useEffect(() => {
    if (!saved) return
    const to = setTimeout(() => setSaved(false), 3000)
    return () => clearTimeout(to)
  }, [saved])

  const daysLeft = useMemo(() => {
    if (!examDate) return null
    const d = new Date(examDate + 'T00:00:00')
    if (Number.isNaN(d.getTime())) return null
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    return Math.round((d.getTime() - now.getTime()) / 86_400_000)
  }, [examDate])

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
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  // Auto-save on add/remove: chip-mutations are deterministic single
  // actions, so persist immediately instead of stranding the change
  // until the user finds the bottom Save button.
  const addTopic = async () => {
    const v = topicDraft.trim().toLowerCase()
    if (!v || topics.includes(v) || topics.length >= 5) return
    const next = [...topics, v]
    setTopics(next)
    setTopicDraft('')
    await save({ topics: next })
  }

  const removeTopic = async (t: string) => {
    const next = topics.filter((x) => x !== t)
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
            className={`shrink-0 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors duration-fast ${
              activeTab === key
                ? 'text-primary border-primary'
                : 'text-muted-fg border-transparent hover:text-fg'
            }`}
          >
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
              <div>
                <label htmlFor="goals-exam" className="text-sm font-semibold text-fg block mb-1">
                  {t('examDate.label')}
                </label>
                <input
                  id="goals-exam"
                  type="date"
                  value={examDate}
                  onChange={(e) => setExamDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                />
                {daysLeft !== null && daysLeft >= 0 && (
                  <p className={`text-xs mt-1 font-medium ${daysLeft <= 30 ? 'text-danger' : 'text-warning'}`}>
                    {t('examDate.daysLeft', { count: daysLeft })}
                    {daysLeft <= 30 && t('examDate.urgentSuffix')}
                  </p>
                )}
                {examDate && (
                  <button
                    onClick={() => setExamDate('')}
                    className="text-xs text-muted-fg hover:text-fg mt-1 underline"
                  >
                    {t('examDate.clear')}
                  </button>
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

              <div>
                <label className="text-sm font-semibold text-fg block mb-1">
                  {t('practice.topics')}
                </label>
                <p className="text-xs text-muted-fg mb-2">{t('practice.topicsHint')}</p>
                <div className="flex flex-wrap gap-2 mb-2">
                  {topics.map((topic) => (
                    <span
                      key={topic}
                      className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-sm text-primary"
                    >
                      {topic}
                      <button
                        type="button"
                        onClick={() => removeTopic(topic)}
                        aria-label={t('practice.removeTopic', { topic })}
                        className="text-primary/70 hover:text-primary"
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  {/* Input giữ enabled để user gõ được; chỉ Add button +
                      hint phía dưới mới phản ánh giới hạn 5. */}
                  <input
                    type="text"
                    value={topicDraft}
                    onChange={(e) => setTopicDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addTopic()
                      }
                    }}
                    placeholder={t('practice.topicsPlaceholder')}
                    className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={addTopic}
                    disabled={!topicDraft.trim() || topics.length >= 5 || saving}
                    className="px-3 py-2 rounded-lg bg-primary text-primary-fg text-sm hover:bg-primary-hover disabled:opacity-50"
                  >
                    {t('common:actions.add')}
                  </button>
                </div>
                {topics.length >= 5 && (
                  <p className="text-xs text-warning mt-1">
                    {t('practice.topicsFull')}
                  </p>
                )}
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
                  className="px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
                />
                <p className="text-xs text-muted-fg mt-1">
                  {t('practice.dailyTimeHint', { tz: timezone })}
                </p>
              </div>

              {/* topics chips auto-save on add/remove. The Save button
                  on this tab persists daily_time only. */}
              <button
                onClick={() => save({ daily_time: dailyTime || '' })}
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
                <div className="flex items-center justify-between">
                  <span className="text-sm text-fg">{t('usage:page.settingsLink')}</span>
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
              <Link
                to="/settings/link-telegram"
                className="block rounded-lg border border-border bg-surface p-3 hover:bg-surface-raised"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-fg">{t('link:settings.heading')}</p>
                    <p className="text-xs text-muted-fg mt-1">
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
    </div>
  )
}
