import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import AdminButton from '../../components/admin/AdminButton'
import AdminCard, { AdminPageHeader } from '../../components/admin/AdminCard'
import AdminInput, { AdminField } from '../../components/admin/AdminInput'
import { apiFetch } from '../../lib/api'

interface FlagRow {
  name: string
  enabled: boolean
  rollout_pct: number
  uid_allowlist: string[]
  description: string
  updated_at: string | null
}

interface FlagDraft {
  name: string
  enabled: boolean
  rollout_pct: number
  allowlistText: string
  description: string
}

const EMPTY_DRAFT: FlagDraft = {
  name: '',
  enabled: false,
  rollout_pct: 0,
  allowlistText: '',
  description: '',
}

function parseAllowlist(text: string): string[] {
  return text
    .split(/\r?\n|,/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export default function FlagsPage() {
  const { t } = useTranslation('admin')
  const { t: tCommon } = useTranslation('common')

  const [rows, setRows] = useState<FlagRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<FlagDraft | null>(null) // null = list view
  const [creating, setCreating] = useState(false)

  async function refresh() {
    setError(null)
    try {
      setRows(await apiFetch<FlagRow[]>('/api/v1/admin/flags'))
    } catch {
      setError(t('common.error'))
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function startCreate() {
    setCreating(true)
    setDraft(EMPTY_DRAFT)
  }

  function startEdit(row: FlagRow) {
    setCreating(false)
    setDraft({
      name: row.name,
      enabled: row.enabled,
      rollout_pct: row.rollout_pct,
      allowlistText: row.uid_allowlist.join('\n'),
      description: row.description,
    })
  }

  function cancel() {
    setDraft(null)
    setCreating(false)
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!draft) return
    setError(null)
    try {
      await apiFetch(
        `/api/v1/admin/flags/${encodeURIComponent(draft.name)}`,
        {
          method: 'PUT',
          body: JSON.stringify({
            enabled: draft.enabled,
            rollout_pct: draft.rollout_pct,
            uid_allowlist: parseAllowlist(draft.allowlistText),
            description: draft.description,
          }),
        },
      )
      cancel()
      await refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  async function remove(name: string) {
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/flags/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      })
      await refresh()
    } catch {
      setError(t('common.error'))
    }
  }

  return (
    <>
      <AdminPageHeader
        title={t('flags.title')}
        actions={
          !draft ? (
            <AdminButton type="button" onClick={startCreate}>
              {t('flags.form.save')}
            </AdminButton>
          ) : undefined
        }
      />

      {error && <p className="text-danger text-sm">{error}</p>}

      {draft && (
        <AdminCard>
          <form onSubmit={save} className="space-y-4">
            <AdminField label={t('flags.form.name')}>
              <AdminInput
                type="text"
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                disabled={!creating}
                className="disabled:opacity-60"
                required
              />
            </AdminField>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) =>
                  setDraft({ ...draft, enabled: e.target.checked })
                }
              />
              <span className="text-sm font-medium">{t('flags.form.enabled')}</span>
            </label>
            <AdminField label={t('flags.form.rollout')}>
              <input
                type="range"
                min={0}
                max={100}
                value={draft.rollout_pct}
                onChange={(e) =>
                  setDraft({ ...draft, rollout_pct: Number(e.target.value) })
                }
                className="block w-full"
              />
              <span className="text-xs text-muted-fg tabular-nums">
                {draft.rollout_pct}%
              </span>
            </AdminField>
            <AdminField label={t('flags.form.allowlist')}>
              <textarea
                value={draft.allowlistText}
                onChange={(e) =>
                  setDraft({ ...draft, allowlistText: e.target.value })
                }
                rows={4}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </AdminField>
            <AdminField label={t('flags.form.description')}>
              <AdminInput
                type="text"
                value={draft.description}
                onChange={(e) =>
                  setDraft({ ...draft, description: e.target.value })
                }
              />
            </AdminField>
            <div className="flex items-center gap-2">
              <AdminButton type="submit">{t('flags.form.save')}</AdminButton>
              <AdminButton type="button" variant="secondary" onClick={cancel}>
                {tCommon('actions.cancel')}
              </AdminButton>
            </div>
          </form>
        </AdminCard>
      )}

      {rows === null && !error && (
        <p className="text-muted-fg">{t('common.loading')}</p>
      )}

      {rows !== null && rows.length === 0 && (
        <p className="text-muted-fg">{t('flags.empty')}</p>
      )}

      {rows !== null && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-raised">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-border bg-surface">
                <th className="px-4 py-2">{t('flags.table.name')}</th>
                <th className="px-4 py-2">{t('flags.table.enabled')}</th>
                <th className="px-4 py-2">{t('flags.table.rollout')}</th>
                <th className="px-4 py-2">{t('flags.table.allowlist')}</th>
                <th className="px-4 py-2">{t('flags.table.description')}</th>
                <th className="px-4 py-2">{t('flags.table.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.name} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{f.name}</td>
                  <td className="px-4 py-2">
                    <span
                      className={
                        f.enabled
                          ? 'text-success font-medium'
                          : 'text-muted-fg'
                      }
                    >
                      {f.enabled ? '●' : '○'}
                    </span>
                  </td>
                  <td className="px-4 py-2 tabular-nums">{f.rollout_pct}%</td>
                  <td className="px-4 py-2 text-xs text-muted-fg">
                    {f.uid_allowlist.length}
                  </td>
                  <td className="px-4 py-2 text-muted-fg">
                    {f.description || '—'}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <AdminButton
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => startEdit(f)}
                      >
                        {tCommon('actions.edit')}
                      </AdminButton>
                      <AdminButton
                        type="button"
                        variant="danger"
                        size="sm"
                        onClick={() => remove(f.name)}
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
