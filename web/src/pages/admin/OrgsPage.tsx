import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

interface AdminOrgSummary {
  id: string
  name: string
  owner_uid: string
  plan_id: string
  plan_expires_at: string | null
  created_at: string | null
  admin_count: number
  team_count: number
}

const PLANS = ['org_member', 'team_member', 'personal_pro', 'free'] as const

export default function OrgsPage() {
  const { t } = useTranslation('admin')
  const { t: tCommon } = useTranslation('common')

  const [rows, setRows] = useState<AdminOrgSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const [name, setName] = useState('')
  const [ownerUid, setOwnerUid] = useState('')
  const [planId, setPlanId] = useState<string>('org_member')

  function refresh() {
    setError(null)
    apiFetch<AdminOrgSummary[]>('/api/v1/admin/orgs')
      .then(setRows)
      .catch(() => setError(t('common.error')))
  }

  useEffect(refresh, [t])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !ownerUid.trim()) return
    setCreating(true)
    setError(null)
    try {
      await apiFetch('/api/v1/admin/orgs', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          owner_uid: ownerUid.trim(),
          plan_id: planId,
        }),
      })
      setName('')
      setOwnerUid('')
      refresh()
    } catch {
      setError(t('common.error'))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="px-4 md:px-6 py-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('orgs.title')}</h1>
      </div>

      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-border bg-surface-raised p-4 grid grid-cols-1 sm:grid-cols-4 gap-3"
      >
        <input
          type="text"
          placeholder={t('orgs.form.name')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface sm:col-span-2"
        />
        <input
          type="text"
          placeholder={t('orgs.form.ownerUid')}
          value={ownerUid}
          onChange={(e) => setOwnerUid(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        />
        <div className="flex gap-2">
          <select
            value={planId}
            onChange={(e) => setPlanId(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface flex-1"
          >
            {PLANS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={creating || !name.trim() || !ownerUid.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium disabled:opacity-50"
          >
            {t('orgs.form.create')}
          </button>
        </div>
      </form>

      {error && <p className="text-danger text-sm">{error}</p>}

      {rows === null && !error && (
        <p className="text-muted-fg">{t('common.loading')}</p>
      )}

      {rows !== null && rows.length === 0 && (
        <p className="text-muted-fg">{t('orgs.empty')}</p>
      )}

      {rows !== null && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-raised">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-border bg-surface">
                <th className="px-4 py-2">{t('orgs.table.name')}</th>
                <th className="px-4 py-2">{t('orgs.table.plan')}</th>
                <th className="px-4 py-2">{t('orgs.table.admins')}</th>
                <th className="px-4 py-2">{t('orgs.table.teams')}</th>
                <th className="px-4 py-2">{t('orgs.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-medium">{row.name}</td>
                  <td className="px-4 py-2">{row.plan_id}</td>
                  <td className="px-4 py-2 tabular-nums">{row.admin_count}</td>
                  <td className="px-4 py-2 tabular-nums">{row.team_count}</td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/admin/orgs/${encodeURIComponent(row.id)}`}
                      className="text-primary underline"
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
    </div>
  )
}
