import { useEffect, useMemo, useState } from 'react'
import Icon from '../components/Icon'
import { apiFetch } from '../lib/api'
import { ThemePref, useTheme } from '../lib/theme'

const THEME_OPTIONS: { value: ThemePref; label: string }[] = [
  { value: 'system', label: 'Hệ thống' },
  { value: 'light', label: 'Sáng' },
  { value: 'dark', label: 'Tối' },
]

function ThemeToggle() {
  const { pref, setPref } = useTheme()
  return (
    <div>
      <label id="theme-label" className="text-sm font-semibold text-fg block mb-1">
        Giao diện
      </label>
      <div
        role="radiogroup"
        aria-labelledby="theme-label"
        className="inline-flex rounded-lg border border-border bg-surface-raised overflow-hidden"
      >
        {THEME_OPTIONS.map((o) => (
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

interface UserProfile {
  id: string
  name: string
  email: string | null
  target_band: number
  topics: string[]
  streak: number
  exam_date: string | null
  weekly_goal_minutes: number
}

export default function SettingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [examDate, setExamDate] = useState('')
  const [weeklyGoal, setWeeklyGoal] = useState<number>(150)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => {
        setProfile(p)
        setExamDate(p.exam_date ?? '')
        setWeeklyGoal(p.weekly_goal_minutes ?? 150)
      })
      .catch((e) => setError((e as Error).message))
  }, [])

  const daysLeft = useMemo(() => {
    if (!examDate) return null
    const d = new Date(examDate + 'T00:00:00')
    if (Number.isNaN(d.getTime())) return null
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    return Math.round((d.getTime() - now.getTime()) / 86_400_000)
  }, [examDate])

  const save = async () => {
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      const updated = await apiFetch<UserProfile>('/api/v1/me', {
        method: 'PATCH',
        body: JSON.stringify({
          exam_date: examDate || '',
          weekly_goal_minutes: weeklyGoal,
        }),
      })
      setProfile(updated)
      setSaved(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  // Auto-dismiss the saved confirmation after 3s (audit #15)
  useEffect(() => {
    if (!saved) return
    const t = setTimeout(() => setSaved(false), 3000)
    return () => clearTimeout(t)
  }, [saved])

  return (
    <div className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Cài đặt</h1>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {saved && (
        <div
          role="status"
          aria-live="polite"
          className="bg-success/10 border-l-4 border-success p-3 rounded text-sm text-success"
        >
          Đã lưu cài đặt.
        </div>
      )}

      <div className="bg-surface-raised rounded-xl border border-border p-4 space-y-4">
        <ThemeToggle />

        <div>
          <label className="text-sm font-semibold text-fg block mb-1">
            Ngày thi IELTS
          </label>
          <input
            type="date"
            value={examDate}
            onChange={(e) => setExamDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:border-indigo-400 focus:outline-none"
          />
          {daysLeft !== null && daysLeft >= 0 && (
            <p
              className={`text-xs mt-1 font-medium ${
                daysLeft <= 30 ? 'text-red-600' : 'text-amber-600'
              }`}
            >
              Còn {daysLeft} ngày nữa. {daysLeft <= 30 && 'Kế hoạch sẽ tăng cường.'}
            </p>
          )}
          {daysLeft !== null && daysLeft < 0 && (
            <p className="text-xs mt-1 text-gray-500">Ngày đã qua.</p>
          )}
          {examDate && (
            <button
              onClick={() => setExamDate('')}
              className="text-xs text-gray-500 hover:text-gray-700 mt-1 underline"
            >
              Xóa ngày thi
            </button>
          )}
        </div>

        <div>
          <label className="text-sm font-semibold text-gray-800 block mb-1">
            Mục tiêu mỗi tuần (phút)
          </label>
          <input
            type="number"
            min={30}
            max={2000}
            step={10}
            value={weeklyGoal}
            onChange={(e) => setWeeklyGoal(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:border-indigo-400 focus:outline-none"
          />
          <p className="text-xs text-gray-500 mt-1">
            Trung bình {Math.round(weeklyGoal / 7)} phút mỗi ngày.
          </p>
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="w-full py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? 'Đang lưu...' : 'Lưu'}
        </button>
      </div>

      {profile && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-sm text-gray-600 space-y-1">
          <p><span className="text-gray-500">Tên:</span> {profile.name}</p>
          {profile.email && <p><span className="text-gray-500">Email:</span> {profile.email}</p>}
          <p>
            <span className="text-gray-500">Band mục tiêu:</span> {profile.target_band}
          </p>
          <p className="inline-flex items-center gap-1">
            <span className="text-gray-500">Streak:</span>
            <Icon name="Flame" size="sm" variant="accent" />
            {profile.streak}
          </p>
        </div>
      )}
    </div>
  )
}
