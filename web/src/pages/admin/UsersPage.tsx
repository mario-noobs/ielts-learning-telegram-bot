import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import AdminCard, { AdminPageHeader } from '../../components/admin/AdminCard'
import AdminInput, { AdminSelect } from '../../components/admin/AdminInput'
import Pagination from '../../components/Pagination'
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

interface ListResponse {
  items: AdminUserSummary[]
  total: number
  page: number
  page_size: number
}

const PAGE_SIZE = 50
const ROLES = ['user', 'team_admin', 'org_admin', 'platform_admin'] as const
const PLANS = ['free', 'personal_pro', 'team_member', 'org_member'] as const

export default function UsersPage() {
  const { t } = useTranslation('admin')
  const { t: tCommon } = useTranslation('common')
  const [page, setPage] = useState(1)
  const [role, setRole] = useState('')
  const [plan, setPlan] = useState('')
  const [q, setQ] = useState('')
  const [data, setData] = useState<ListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    })
    if (role) params.set('role', role)
    if (plan) params.set('plan', plan)
    if (q) params.set('q', q)

    setError(null)
    let cancelled = false
    apiFetch<ListResponse>(`/api/v1/admin/users?${params}`)
      .then((r) => {
        if (!cancelled) setData(r)
      })
      .catch(() => {
        if (!cancelled) setError(t('common.error'))
      })
    return () => {
      cancelled = true
    }
  }, [page, role, plan, q, t])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <AdminPageHeader title={t('users.title')} />

      <AdminCard>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <AdminInput
            type="text"
            placeholder={t('users.filters.search')}
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
          />
          <AdminSelect
            value={role}
            onChange={(e) => {
              setRole(e.target.value)
              setPage(1)
            }}
          >
            <option value="">{t('users.filters.anyRole')}</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </AdminSelect>
          <AdminSelect
            value={plan}
            onChange={(e) => {
              setPlan(e.target.value)
              setPage(1)
            }}
          >
            <option value="">{t('users.filters.anyPlan')}</option>
            {PLANS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </AdminSelect>
        </div>
      </AdminCard>

      {error && <p className="text-danger text-sm">{error}</p>}

      {data === null && !error && (
        <p className="text-muted-fg">{t('common.loading')}</p>
      )}

      {data !== null && data.items.length === 0 && (
        <p className="text-muted-fg">{t('users.empty')}</p>
      )}

      {data !== null && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-raised">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-border bg-surface">
                <th className="px-4 py-2">{t('users.table.name')}</th>
                <th className="px-4 py-2">{t('users.table.email')}</th>
                <th className="px-4 py-2">{t('users.table.role')}</th>
                <th className="px-4 py-2">{t('users.table.plan')}</th>
                <th className="px-4 py-2">{t('users.table.lastActive')}</th>
                <th className="px-4 py-2">{t('users.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-medium">{u.name || u.id}</td>
                  <td className="px-4 py-2 text-muted-fg">{u.email ?? '—'}</td>
                  <td className="px-4 py-2">{t(`roles.${u.role}`)}</td>
                  <td className="px-4 py-2">{u.plan}</td>
                  <td className="px-4 py-2 text-muted-fg">
                    {u.last_active_date ?? '—'}
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/admin/users/${encodeURIComponent(u.id)}`}
                      className="text-primary hover:underline text-sm"
                    >
                      {tCommon('actions.edit')}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data !== null && totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
        />
      )}
    </>
  )
}
