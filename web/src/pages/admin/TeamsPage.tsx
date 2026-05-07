import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
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

const PLANS = ['team_member', 'org_member', 'personal_pro', 'free'] as const

export default function TeamsPage() {
  const { t } = useTranslation('admin')
  const { t: tCommon } = useTranslation('common')

  const [rows, setRows] = useState<AdminTeamSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  // Create form
  const [name, setName] = useState('')
  const [ownerUid, setOwnerUid] = useState('')
  const [planId, setPlanId] = useState<string>('team_member')
  const [seatLimit, setSeatLimit] = useState('5')

  function refresh() {
    setError(null)
    apiFetch<AdminTeamSummary[]>('/api/v1/admin/teams')
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
      await apiFetch('/api/v1/admin/teams', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          owner_uid: ownerUid.trim(),
          plan_id: planId,
          seat_limit: Math.max(1, Number(seatLimit) || 1),
        }),
      })
      setName('')
      setOwnerUid('')
      setSeatLimit('5')
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
        <h1 className="text-2xl font-semibold">{t('teams.title')}</h1>
      </div>

      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-border bg-surface-raised p-4 grid grid-cols-1 sm:grid-cols-5 gap-3"
      >
        <input
          type="text"
          placeholder={t('teams.form.name')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface sm:col-span-2"
        />
        <input
          type="text"
          placeholder={t('teams.form.ownerUid')}
          value={ownerUid}
          onChange={(e) => setOwnerUid(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        />
        <select
          value={planId}
          onChange={(e) => setPlanId(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        >
          {PLANS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <div className="flex gap-2">
          <input
            type="number"
            min={1}
            max={10000}
            value={seatLimit}
            onChange={(e) => setSeatLimit(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface w-24"
            aria-label={t('teams.form.seatLimit')}
          />
          <button
            type="submit"
            disabled={creating || !name.trim() || !ownerUid.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium disabled:opacity-50"
          >
            {t('teams.form.create')}
          </button>
        </div>
      </form>

      {error && <p className="text-danger text-sm">{error}</p>}

      {rows === null && !error && (
        <p className="text-muted-fg">{t('common.loading')}</p>
      )}

      {rows !== null && rows.length === 0 && (
        <p className="text-muted-fg">{t('teams.empty')}</p>
      )}

      {rows !== null && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-raised">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-border bg-surface">
                <th className="px-4 py-2">{t('teams.table.name')}</th>
                <th className="px-4 py-2">{t('teams.table.plan')}</th>
                <th className="px-4 py-2">{t('teams.table.seats')}</th>
                <th className="px-4 py-2">{t('teams.table.members')}</th>
                <th className="px-4 py-2">{t('teams.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-medium">{row.name}</td>
                  <td className="px-4 py-2">{row.plan_id}</td>
                  <td className="px-4 py-2 tabular-nums">{row.seat_limit}</td>
                  <td className="px-4 py-2 tabular-nums">{row.member_count}</td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/admin/teams/${encodeURIComponent(row.id)}`}
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
