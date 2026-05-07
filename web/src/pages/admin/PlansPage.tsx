import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
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
    <div className="px-4 md:px-6 py-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('plans.title')}</h1>
        {!creating && !editingId && (
          <button
            type="button"
            onClick={startCreate}
            className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium"
          >
            {t('plans.createCta')}
          </button>
        )}
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      {(creating || editingId) && (
        <form
          onSubmit={submit}
          className="space-y-3 rounded-xl border border-border bg-surface-raised p-4"
        >
          {creating && (
            <label className="block">
              <span className="text-sm font-medium">{t('plans.form.id')}</span>
              <input
                type="text"
                value={form.id}
                onChange={(e) => setForm({ ...form, id: e.target.value })}
                className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
                required
              />
              <p className="text-xs text-muted-fg mt-1">{t('plans.form.idHint')}</p>
            </label>
          )}
          <label className="block">
            <span className="text-sm font-medium">{t('plans.form.name')}</span>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
              required
            />
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="block">
              <span className="text-sm font-medium">{t('plans.form.dailyQuota')}</span>
              <input
                type="number"
                min={0}
                value={form.daily_ai_quota}
                onChange={(e) => setForm({ ...form, daily_ai_quota: Number(e.target.value) })}
                className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t('plans.form.monthlyQuota')}</span>
              <input
                type="number"
                min={0}
                value={form.monthly_ai_quota}
                onChange={(e) => setForm({ ...form, monthly_ai_quota: Number(e.target.value) })}
                className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t('plans.form.maxSeats')}</span>
              <input
                type="number"
                min={1}
                value={form.max_team_seats ?? ''}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_team_seats: e.target.value === '' ? null : Number(e.target.value),
                  })
                }
                className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
              />
            </label>
          </div>
          <label className="block">
            <span className="text-sm font-medium">{t('plans.form.features')}</span>
            <input
              type="text"
              value={featuresToText(form.features)}
              onChange={(e) =>
                setForm({ ...form, features: textToFeatures(e.target.value) })
              }
              className="mt-1 block w-full px-3 py-2 rounded-lg border border-border bg-surface"
            />
          </label>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-primary text-on-primary font-medium"
            >
              {creating ? t('plans.form.create') : t('plans.form.save')}
            </button>
            <button
              type="button"
              onClick={cancel}
              className="px-4 py-2 rounded-lg border border-border"
            >
              {t('plans.form.cancel')}
            </button>
          </div>
        </form>
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
                  <td className="px-4 py-2 space-x-2">
                    <button
                      type="button"
                      onClick={() => startEdit(p)}
                      className="text-primary underline"
                    >
                      {tCommon('actions.edit')}
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(p.id)}
                      className="text-danger underline"
                    >
                      {tCommon('actions.delete')}
                    </button>
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
