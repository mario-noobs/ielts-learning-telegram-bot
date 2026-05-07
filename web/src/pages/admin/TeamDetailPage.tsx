import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

interface AdminTeamSummary {
  id: string
  name: string
  owner_uid: string
  plan_id: string
  plan_expires_at: string | null
  seat_limit: number
  created_by: string
  created_at: string | null
  member_count: number
}

interface AdminTeamMemberRow {
  user_uid: string
  role: string
  joined_at: string | null
}

const ROLES = ['member', 'admin'] as const

export default function TeamDetailPage() {
  const { t } = useTranslation('admin')
  const { id = '' } = useParams<{ id: string }>()

  const [team, setTeam] = useState<AdminTeamSummary | null>(null)
  const [members, setMembers] = useState<AdminTeamMemberRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Edit form
  const [name, setName] = useState('')
  const [seatLimit, setSeatLimit] = useState('1')

  // Add-member form
  const [newUid, setNewUid] = useState('')
  const [newRole, setNewRole] = useState<'member' | 'admin'>('member')

  function refresh() {
    if (!id) return
    setError(null)
    Promise.all([
      apiFetch<AdminTeamSummary>(`/api/v1/admin/teams/${encodeURIComponent(id)}`),
      apiFetch<AdminTeamMemberRow[]>(
        `/api/v1/admin/teams/${encodeURIComponent(id)}/members`,
      ),
    ])
      .then(([row, ms]) => {
        setTeam(row)
        setMembers(ms)
        setName(row.name)
        setSeatLimit(String(row.seat_limit))
      })
      .catch(() => setError(t('common.error')))
  }

  useEffect(refresh, [id, t])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!team) return
    const body: Record<string, unknown> = {}
    if (name !== team.name) body.name = name
    const seatNum = Math.max(1, Number(seatLimit) || 1)
    if (seatNum !== team.seat_limit) body.seat_limit = seatNum
    if (Object.keys(body).length === 0) return
    setSaving(true)
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/teams/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      refresh()
    } catch {
      setError(t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault()
    if (!newUid.trim()) return
    setError(null)
    try {
      await apiFetch(
        `/api/v1/admin/teams/${encodeURIComponent(id)}/members`,
        {
          method: 'POST',
          body: JSON.stringify({ user_uid: newUid.trim(), role: newRole }),
        },
      )
      setNewUid('')
      setNewRole('member')
      refresh()
    } catch (err: unknown) {
      const e2 = err as { code?: string }
      if (e2?.code === 'team.seat_limit_reached') {
        setError(t('teams.errors.seatLimitReached'))
      } else if (e2?.code === 'team.member_already_exists') {
        setError(t('teams.errors.memberAlreadyExists'))
      } else {
        setError(t('common.error'))
      }
    }
  }

  async function handleRemoveMember(uid: string) {
    setError(null)
    try {
      await apiFetch(
        `/api/v1/admin/teams/${encodeURIComponent(id)}/members/${encodeURIComponent(uid)}`,
        { method: 'DELETE' },
      )
      refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  return (
    <div className="px-4 md:px-6 py-6 max-w-3xl mx-auto space-y-6">
      <Link to="/admin/teams" className="text-primary underline text-sm">
        ← {t('teams.detail.back')}
      </Link>

      <div>
        <h1 className="text-2xl font-semibold">{team?.name || id}</h1>
        {team && (
          <p className="text-muted-fg text-sm">
            {team.plan_id} · {team.member_count} / {team.seat_limit}
          </p>
        )}
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}
      {!team && !error && <p className="text-muted-fg">{t('common.loading')}</p>}

      {team && (
        <form
          onSubmit={handleSave}
          className="space-y-4 rounded-xl border border-border bg-surface-raised p-4"
        >
          <label className="block">
            <span className="text-sm font-medium">{t('teams.form.name')}</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t('teams.form.seatLimit')}</span>
            <input
              type="number"
              min={1}
              max={10000}
              value={seatLimit}
              onChange={(e) => setSeatLimit(e.target.value)}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium disabled:opacity-50"
          >
            {saving ? t('common.loading') : t('users.detail.save')}
          </button>
        </form>
      )}

      <div className="rounded-xl border border-border bg-surface-raised p-4 space-y-4">
        <h2 className="text-lg font-semibold">{t('teams.detail.members')}</h2>
        <form
          onSubmit={handleAddMember}
          className="grid grid-cols-1 sm:grid-cols-3 gap-3"
        >
          <input
            type="text"
            placeholder={t('teams.detail.addMemberUid')}
            value={newUid}
            onChange={(e) => setNewUid(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface sm:col-span-2"
          />
          <div className="flex gap-2">
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as 'member' | 'admin')}
              className="px-3 py-2 rounded-lg border border-border bg-surface flex-1"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`teams.memberRoles.${r}`)}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={!newUid.trim()}
              className="px-3 py-2 rounded-lg bg-primary text-on-primary text-sm disabled:opacity-50"
            >
              {t('teams.detail.add')}
            </button>
          </div>
        </form>

        {members && members.length === 0 && (
          <p className="text-muted-fg text-sm">{t('teams.detail.noMembers')}</p>
        )}
        {members && members.length > 0 && (
          <table className="w-full text-sm">
            <tbody>
              {members.map((m) => (
                <tr key={m.user_uid} className="border-b border-border last:border-0">
                  <td className="py-1.5">{m.user_uid}</td>
                  <td className="py-1.5 text-muted-fg">
                    {t(`teams.memberRoles.${m.role}`)}
                  </td>
                  <td className="py-1.5 text-right">
                    <button
                      type="button"
                      onClick={() => handleRemoveMember(m.user_uid)}
                      className="text-danger underline text-xs"
                    >
                      {t('teams.detail.remove')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
