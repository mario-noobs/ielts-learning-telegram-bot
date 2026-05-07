import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import AdminButton from '../../components/admin/AdminButton'
import AdminCard from '../../components/admin/AdminCard'
import AdminInput, { AdminField, AdminSelect } from '../../components/admin/AdminInput'
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
    <>
      <Link to="/admin/users" className="text-primary hover:underline text-sm">
        ← {t('users.detail.back')}
      </Link>

      <div>
        <h1 className="text-2xl font-semibold">{user?.name || id}</h1>
        {user?.email && <p className="text-muted-fg text-sm">{user.email}</p>}
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!user && !error && <p className="text-muted-fg">{t('common.loading')}</p>}

      {user && (
        <AdminCard>
          <form onSubmit={handleSave} className="space-y-4">
            <AdminField label={t('users.detail.role')}>
              <AdminSelect
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`roles.${r}`)}
                  </option>
                ))}
              </AdminSelect>
            </AdminField>

            <AdminField label={t('users.detail.plan')}>
              <AdminSelect
                value={plan}
                onChange={(e) => setPlan(e.target.value)}
              >
                {PLANS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </AdminSelect>
            </AdminField>

            <AdminField label={t('users.detail.planExpiresAt')}>
              <AdminInput
                type="date"
                value={planExpires}
                onChange={(e) => setPlanExpires(e.target.value)}
              />
            </AdminField>

            <AdminField
              label={t('users.detail.quotaOverride')}
              hint={t('users.detail.quotaOverrideHint')}
            >
              <AdminInput
                type="number"
                min={0}
                value={quotaOverride}
                onChange={(e) => setQuotaOverride(e.target.value)}
              />
            </AdminField>

            <div className="flex items-center gap-3">
              <AdminButton type="submit" disabled={saving}>
                {saving ? t('common.loading') : t('users.detail.save')}
              </AdminButton>
              {savedAt !== null && !saving && (
                <span className="text-sm text-success">
                  {t('users.detail.saved')}
                </span>
              )}
            </div>
          </form>
        </AdminCard>
      )}

      {usage && (
        <AdminCard title={t('users.detail.recentUsage')}>
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
        </AdminCard>
      )}
    </>
  )
}
