import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import AdminButton from '../../components/admin/AdminButton'
import AdminCard from '../../components/admin/AdminCard'
import AdminInput, { AdminField } from '../../components/admin/AdminInput'
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
    <>
      <Link to="/admin/orgs" className="text-primary hover:underline text-sm">
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
        <AdminCard>
          <form onSubmit={handleSave} className="space-y-4">
            <AdminField label={t('orgs.form.name')}>
              <AdminInput
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </AdminField>
            <AdminButton type="submit" disabled={saving || name === org.name}>
              {saving ? t('common.loading') : t('users.detail.save')}
            </AdminButton>
          </form>
        </AdminCard>
      )}

      <AdminCard title={t('orgs.detail.admins')}>
        <form onSubmit={handleAddAdmin} className="flex gap-2">
          <AdminInput
            type="text"
            placeholder={t('orgs.detail.addAdminUid')}
            value={newAdminUid}
            onChange={(e) => setNewAdminUid(e.target.value)}
            className="flex-1"
          />
          <AdminButton type="submit" disabled={!newAdminUid.trim()}>
            {t('orgs.detail.add')}
          </AdminButton>
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
                <AdminButton
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={() => handleRemoveAdmin(uid)}
                >
                  {t('orgs.detail.remove')}
                </AdminButton>
              </li>
            ))}
          </ul>
        )}
      </AdminCard>

      <AdminCard title={t('orgs.detail.teams')}>
        <form onSubmit={handleLinkTeam} className="flex gap-2">
          <AdminInput
            type="text"
            placeholder={t('orgs.detail.linkTeamId')}
            value={newTeamId}
            onChange={(e) => setNewTeamId(e.target.value)}
            className="flex-1"
          />
          <AdminButton type="submit" disabled={!newTeamId.trim()}>
            {t('orgs.detail.link')}
          </AdminButton>
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
                  className="text-primary hover:underline"
                >
                  {tid}
                </Link>
                <AdminButton
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={() => handleUnlinkTeam(tid)}
                >
                  {t('orgs.detail.unlink')}
                </AdminButton>
              </li>
            ))}
          </ul>
        )}
      </AdminCard>
    </>
  )
}
