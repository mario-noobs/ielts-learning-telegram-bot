import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
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

export default function OrgDetailPage() {
  const { t } = useTranslation('admin')
  const { id = '' } = useParams<{ id: string }>()

  const [org, setOrg] = useState<AdminOrgSummary | null>(null)
  const [admins, setAdmins] = useState<string[] | null>(null)
  const [teams, setTeams] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [name, setName] = useState('')
  const [newAdminUid, setNewAdminUid] = useState('')
  const [newTeamId, setNewTeamId] = useState('')

  function refresh() {
    if (!id) return
    setError(null)
    Promise.all([
      apiFetch<AdminOrgSummary>(`/api/v1/admin/orgs/${encodeURIComponent(id)}`),
      apiFetch<string[]>(`/api/v1/admin/orgs/${encodeURIComponent(id)}/admins`),
      apiFetch<string[]>(`/api/v1/admin/orgs/${encodeURIComponent(id)}/teams`),
    ])
      .then(([row, a, ts]) => {
        setOrg(row)
        setAdmins(a)
        setTeams(ts)
        setName(row.name)
      })
      .catch(() => setError(t('common.error')))
  }

  useEffect(refresh, [id, t])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!org) return
    if (name === org.name) return
    setSaving(true)
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/orgs/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify({ name }),
      })
      refresh()
    } catch {
      setError(t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  async function handleAddAdmin(e: React.FormEvent) {
    e.preventDefault()
    if (!newAdminUid.trim()) return
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/orgs/${encodeURIComponent(id)}/admins`, {
        method: 'POST',
        body: JSON.stringify({ user_uid: newAdminUid.trim() }),
      })
      setNewAdminUid('')
      refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  async function handleRemoveAdmin(uid: string) {
    setError(null)
    try {
      await apiFetch(
        `/api/v1/admin/orgs/${encodeURIComponent(id)}/admins/${encodeURIComponent(uid)}`,
        { method: 'DELETE' },
      )
      refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  async function handleLinkTeam(e: React.FormEvent) {
    e.preventDefault()
    if (!newTeamId.trim()) return
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/orgs/${encodeURIComponent(id)}/teams`, {
        method: 'POST',
        body: JSON.stringify({ team_id: newTeamId.trim() }),
      })
      setNewTeamId('')
      refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  async function handleUnlinkTeam(teamId: string) {
    setError(null)
    try {
      await apiFetch(
        `/api/v1/admin/orgs/${encodeURIComponent(id)}/teams/${encodeURIComponent(teamId)}`,
        { method: 'DELETE' },
      )
      refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  return (
    <div className="px-4 md:px-6 py-6 max-w-3xl mx-auto space-y-6">
      <Link to="/admin/orgs" className="text-primary underline text-sm">
        ← {t('orgs.detail.back')}
      </Link>

      <div>
        <h1 className="text-2xl font-semibold">{org?.name || id}</h1>
        {org && (
          <p className="text-muted-fg text-sm">
            {org.plan_id} · {org.admin_count} {t('orgs.table.admins').toLowerCase()} ·{' '}
            {org.team_count} {t('orgs.table.teams').toLowerCase()}
          </p>
        )}
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!org && !error && <p className="text-muted-fg">{t('common.loading')}</p>}

      {org && (
        <form
          onSubmit={handleSave}
          className="space-y-3 rounded-xl border border-border bg-surface-raised p-4"
        >
          <label className="block">
            <span className="text-sm font-medium">{t('orgs.form.name')}</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            />
          </label>
          <button
            type="submit"
            disabled={saving || name === org.name}
            className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium disabled:opacity-50"
          >
            {saving ? t('common.loading') : t('users.detail.save')}
          </button>
        </form>
      )}

      <div className="rounded-xl border border-border bg-surface-raised p-4 space-y-4">
        <h2 className="text-lg font-semibold">{t('orgs.detail.admins')}</h2>
        <form onSubmit={handleAddAdmin} className="flex gap-2">
          <input
            type="text"
            placeholder={t('orgs.detail.addAdminUid')}
            value={newAdminUid}
            onChange={(e) => setNewAdminUid(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface flex-1"
          />
          <button
            type="submit"
            disabled={!newAdminUid.trim()}
            className="px-3 py-2 rounded-lg bg-primary text-on-primary text-sm disabled:opacity-50"
          >
            {t('orgs.detail.add')}
          </button>
        </form>
        {admins && admins.length === 0 && (
          <p className="text-muted-fg text-sm">{t('orgs.detail.noAdmins')}</p>
        )}
        {admins && admins.length > 0 && (
          <ul className="space-y-1 text-sm">
            {admins.map((uid) => (
              <li
                key={uid}
                className="flex items-center justify-between border-b border-border py-1.5 last:border-0"
              >
                <span>{uid}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveAdmin(uid)}
                  className="text-danger underline text-xs"
                >
                  {t('orgs.detail.remove')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4 space-y-4">
        <h2 className="text-lg font-semibold">{t('orgs.detail.teams')}</h2>
        <form onSubmit={handleLinkTeam} className="flex gap-2">
          <input
            type="text"
            placeholder={t('orgs.detail.linkTeamId')}
            value={newTeamId}
            onChange={(e) => setNewTeamId(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface flex-1"
          />
          <button
            type="submit"
            disabled={!newTeamId.trim()}
            className="px-3 py-2 rounded-lg bg-primary text-on-primary text-sm disabled:opacity-50"
          >
            {t('orgs.detail.link')}
          </button>
        </form>
        {teams && teams.length === 0 && (
          <p className="text-muted-fg text-sm">{t('orgs.detail.noTeams')}</p>
        )}
        {teams && teams.length > 0 && (
          <ul className="space-y-1 text-sm">
            {teams.map((tid) => (
              <li
                key={tid}
                className="flex items-center justify-between border-b border-border py-1.5 last:border-0"
              >
                <Link
                  to={`/admin/teams/${encodeURIComponent(tid)}`}
                  className="text-primary underline"
                >
                  {tid}
                </Link>
                <button
                  type="button"
                  onClick={() => handleUnlinkTeam(tid)}
                  className="text-danger underline text-xs"
                >
                  {t('orgs.detail.unlink')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
