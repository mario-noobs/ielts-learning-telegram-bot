import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

interface AdminUserSummary {
  id: string
  name: string
  email: string | null
  auth_uid: string | null
  role: string
  plan: string
  plan_expires_at: string | null
  quota_override: number | null
  last_active_date: string | null
  created_at: string | null
}

interface UsageResponse {
  user_id: string
  days: number
  points: { date: string; feature: string; count: number }[]
}

const ROLES = ['user', 'team_admin', 'org_admin', 'platform_admin'] as const
const PLANS = ['free', 'personal_pro', 'team_member', 'org_member'] as const

export default function UserDetailPage() {
  const { t } = useTranslation('admin')
  const { id = '' } = useParams<{ id: string }>()

  const [user, setUser] = useState<AdminUserSummary | null>(null)
  const [usage, setUsage] = useState<UsageResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  // Edit-form local state mirrors the row.
  const [role, setRole] = useState('user')
  const [plan, setPlan] = useState('free')
  const [planExpires, setPlanExpires] = useState('')
  const [quotaOverride, setQuotaOverride] = useState('')

  useEffect(() => {
    if (!id) return
    let cancelled = false
    Promise.all([
      apiFetch<AdminUserSummary>(`/api/v1/admin/users/${encodeURIComponent(id)}`),
      apiFetch<UsageResponse>(
        `/api/v1/admin/users/${encodeURIComponent(id)}/usage?days=30`,
      ),
    ])
      .then(([u, usg]) => {
        if (cancelled) return
        setUser(u)
        setUsage(usg)
        setRole(u.role)
        setPlan(u.plan)
        setPlanExpires(u.plan_expires_at ?? '')
        setQuotaOverride(
          u.quota_override === null ? '' : String(u.quota_override),
        )
      })
      .catch(() => {
        if (!cancelled) setError(t('common.error'))
      })
    return () => {
      cancelled = true
    }
  }, [id, t])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    const body: Record<string, unknown> = {}
    if (role !== user?.role) body.role = role
    if (plan !== user?.plan) body.plan = plan
    if (planExpires !== (user?.plan_expires_at ?? '')) {
      body.plan_expires_at = planExpires || null
    }
    const overrideNum = quotaOverride === '' ? null : Number(quotaOverride)
    const oldOverride = user?.quota_override ?? null
    if (overrideNum !== oldOverride) body.quota_override = overrideNum

    if (Object.keys(body).length === 0) {
      setSaving(false)
      setSavedAt(Date.now())
      return
    }

    try {
      await apiFetch(`/api/v1/admin/users/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      // Re-fetch to mirror the server's normalized state.
      const fresh = await apiFetch<AdminUserSummary>(
        `/api/v1/admin/users/${encodeURIComponent(id)}`,
      )
      setUser(fresh)
      setSavedAt(Date.now())
    } catch {
      setError(t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="px-4 md:px-6 py-6 max-w-3xl mx-auto space-y-6">
      <Link to="/admin/users" className="text-primary underline text-sm">
        ← {t('users.detail.back')}
      </Link>

      <div>
        <h1 className="text-2xl font-semibold">{user?.name || id}</h1>
        {user?.email && <p className="text-muted-fg text-sm">{user.email}</p>}
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!user && !error && <p className="text-muted-fg">{t('common.loading')}</p>}

      {user && (
        <form onSubmit={handleSave} className="space-y-4 rounded-xl border border-border bg-surface-raised p-4">
          <label className="block">
            <span className="text-sm font-medium">{t('users.detail.role')}</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">{t('users.detail.plan')}</span>
            <select
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            >
              {PLANS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">{t('users.detail.planExpiresAt')}</span>
            <input
              type="date"
              value={planExpires}
              onChange={(e) => setPlanExpires(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">{t('users.detail.quotaOverride')}</span>
            <input
              type="number"
              min={0}
              value={quotaOverride}
              onChange={(e) => setQuotaOverride(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            />
            <p className="text-xs text-muted-fg mt-1">
              {t('users.detail.quotaOverrideHint')}
            </p>
          </label>

          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium disabled:opacity-50"
          >
            {saving ? t('common.loading') : t('users.detail.save')}
          </button>
          {savedAt !== null && !saving && (
            <span className="ml-3 text-sm text-success">{t('users.detail.saved')}</span>
          )}
        </form>
      )}

      {usage && (
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="text-lg font-semibold mb-3">{t('users.detail.recentUsage')}</h2>
          {usage.points.length === 0 ? (
            <p className="text-muted-fg text-sm">—</p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {usage.points.map((p, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="py-1.5 text-muted-fg">{p.date}</td>
                    <td className="py-1.5">{p.feature}</td>
                    <td className="py-1.5 text-right tabular-nums">{p.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
