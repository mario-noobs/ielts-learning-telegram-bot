import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import AdminButton from '../../components/admin/AdminButton'
import AdminCard, { AdminPageHeader } from '../../components/admin/AdminCard'
import AdminInput, { AdminField } from '../../components/admin/AdminInput'
import { apiFetch } from '../../lib/api'

interface PlanRow {
  id: string
  name: string
  daily_ai_quota: number
  monthly_ai_quota: number
  max_team_seats: number | null
  features: string[]
  created_at: string | null
}

interface PlanForm {
  id: string
  name: string
  daily_ai_quota: number
  monthly_ai_quota: number
  max_team_seats: number | null
  features: string[]
}

const EMPTY_FORM: PlanForm = {
  id: '',
  name: '',
  daily_ai_quota: 0,
  monthly_ai_quota: 0,
  max_team_seats: null,
  features: [],
}

function featuresToText(arr: string[]): string {
  return arr.join(', ')
}

function textToFeatures(s: string): string[] {
  return s.split(',').map((x) => x.trim()).filter(Boolean)
}

export default function PlansPage() {
  const { t } = useTranslation('admin')
  const { t: tCommon } = useTranslation('common')
  const [rows, setRows] = useState<PlanRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<PlanForm>(EMPTY_FORM)

  async function refresh() {
    setError(null)
    try {
      const r = await apiFetch<PlanRow[]>('/api/v1/admin/plans')
      setRows(r)
    } catch {
      setError(t('common.error'))
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function startCreate() {
    setEditingId(null)
    setCreating(true)
    setForm(EMPTY_FORM)
  }

  function startEdit(row: PlanRow) {
    setCreating(false)
    setEditingId(row.id)
    setForm({
      id: row.id,
      name: row.name,
      daily_ai_quota: row.daily_ai_quota,
      monthly_ai_quota: row.monthly_ai_quota,
      max_team_seats: row.max_team_seats,
      features: row.features,
    })
  }

  function cancel() {
    setEditingId(null)
    setCreating(false)
    setForm(EMPTY_FORM)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      if (creating) {
        await apiFetch('/api/v1/admin/plans', {
          method: 'POST',
          body: JSON.stringify(form),
        })
      } else if (editingId) {
        const { id: _id, ...patch } = form
        await apiFetch(`/api/v1/admin/plans/${encodeURIComponent(editingId)}`, {
          method: 'PATCH',
          body: JSON.stringify(patch),
        })
      }
      cancel()
      await refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  async function remove(planId: string) {
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/plans/${encodeURIComponent(planId)}`, {
        method: 'DELETE',
      })
      await refresh()
    } catch (err) {
      // Service-level message includes users_count when applicable.
      const message =
        err instanceof Error && err.message ? err.message : t('common.error')
      setError(message)
    }
  }

  return (
    <>
      <AdminPageHeader
        title={t('plans.title')}
        actions={
          !creating && !editingId ? (
            <AdminButton type="button" onClick={startCreate}>
              {t('plans.createCta')}
            </AdminButton>
          ) : undefined
        }
      />

      {error && <p className="text-danger text-sm">{error}</p>}

      {(creating || editingId) && (
        <AdminCard>
          <form onSubmit={submit} className="space-y-4">
            {creating && (
              <AdminField label={t('plans.form.id')} hint={t('plans.form.idHint')}>
                <AdminInput
                  type="text"
                  value={form.id}
                  onChange={(e) => setForm({ ...form, id: e.target.value })}
                  required
                />
              </AdminField>
            )}
            <AdminField label={t('plans.form.name')}>
              <AdminInput
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </AdminField>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <AdminField label={t('plans.form.dailyQuota')}>
                <AdminInput
                  type="number"
                  min={0}
                  value={form.daily_ai_quota}
                  onChange={(e) =>
                    setForm({ ...form, daily_ai_quota: Number(e.target.value) })
                  }
                />
              </AdminField>
              <AdminField label={t('plans.form.monthlyQuota')}>
                <AdminInput
                  type="number"
                  min={0}
                  value={form.monthly_ai_quota}
                  onChange={(e) =>
                    setForm({ ...form, monthly_ai_quota: Number(e.target.value) })
                  }
                />
              </AdminField>
              <AdminField label={t('plans.form.maxSeats')}>
                <AdminInput
                  type="number"
                  min={1}
                  value={form.max_team_seats ?? ''}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      max_team_seats:
                        e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </AdminField>
            </div>
            <AdminField label={t('plans.form.features')}>
              <AdminInput
                type="text"
                value={featuresToText(form.features)}
                onChange={(e) =>
                  setForm({ ...form, features: textToFeatures(e.target.value) })
                }
              />
            </AdminField>
            <div className="flex items-center gap-2">
              <AdminButton type="submit">
                {creating ? t('plans.form.create') : t('plans.form.save')}
              </AdminButton>
              <AdminButton type="button" variant="secondary" onClick={cancel}>
                {t('plans.form.cancel')}
              </AdminButton>
            </div>
          </form>
        </AdminCard>
      )}

      {rows === null && !error && (
        <p className="text-muted-fg">{t('common.loading')}</p>
      )}

      {rows !== null && rows.length === 0 && (
        <p className="text-muted-fg">{t('plans.empty')}</p>
      )}

      {rows !== null && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-raised">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-border bg-surface">
                <th className="px-4 py-2">{t('plans.table.id')}</th>
                <th className="px-4 py-2">{t('plans.table.name')}</th>
                <th className="px-4 py-2">{t('plans.table.dailyQuota')}</th>
                <th className="px-4 py-2">{t('plans.table.monthlyQuota')}</th>
                <th className="px-4 py-2">{t('plans.table.maxSeats')}</th>
                <th className="px-4 py-2">{t('plans.table.features')}</th>
                <th className="px-4 py-2">{t('plans.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{p.id}</td>
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2 tabular-nums">{p.daily_ai_quota}</td>
                  <td className="px-4 py-2 tabular-nums">{p.monthly_ai_quota}</td>
                  <td className="px-4 py-2 tabular-nums">{p.max_team_seats ?? '—'}</td>
                  <td className="px-4 py-2 text-muted-fg">
                    {p.features.join(', ') || '—'}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <AdminButton
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => startEdit(p)}
                      >
                        {tCommon('actions.edit')}
                      </AdminButton>
                      <AdminButton
                        type="button"
                        variant="danger"
                        size="sm"
                        onClick={() => remove(p.id)}
                      >
                        {tCommon('actions.delete')}
                      </AdminButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
