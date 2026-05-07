import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import Pagination from '../../components/Pagination'
import { apiFetch } from '../../lib/api'

interface AuditRow {
  id: number
  event_type: string
  actor_uid: string
  target_kind: string
  target_id: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  request_id: string | null
  created_at: string | null
}

interface AuditPage {
  items: AuditRow[]
  total: number
  page: number
  page_size: number
}

const PAGE_SIZE = 50

export default function AuditLogPage() {
  const { t } = useTranslation('admin')
  const [params, setParams] = useSearchParams()

  // Form state mirrors the URL query so deep-links round-trip.
  const [actorUid, setActorUid] = useState(params.get('actor_uid') ?? '')
  const [eventType, setEventType] = useState(params.get('event_type') ?? '')
  const [targetKind, setTargetKind] = useState(params.get('target_kind') ?? '')
  const [since, setSince] = useState(params.get('since') ?? '')
  const [until, setUntil] = useState(params.get('until') ?? '')
  const page = Math.max(1, Number(params.get('page')) || 1)

  const [eventTypes, setEventTypes] = useState<string[]>([])
  const [data, setData] = useState<AuditPage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<string[]>('/api/v1/admin/audit/event-types')
      .then(setEventTypes)
      .catch(() => {/* non-blocking */})
  }, [])

  const queryString = useMemo(() => {
    const q = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    })
    if (actorUid) q.set('actor_uid', actorUid)
    if (eventType) q.set('event_type', eventType)
    if (targetKind) q.set('target_kind', targetKind)
    if (since) q.set('since', since)
    if (until) q.set('until', until)
    return q.toString()
  }, [page, actorUid, eventType, targetKind, since, until])

  useEffect(() => {
    setError(null)
    let cancelled = false
    apiFetch<AuditPage>(`/api/v1/admin/audit?${queryString}`)
      .then((r) => {
        if (!cancelled) setData(r)
      })
      .catch(() => {
        if (!cancelled) setError(t('common.error'))
      })
    return () => {
      cancelled = true
    }
  }, [queryString, t])

  function applyFilters(e: React.FormEvent) {
    e.preventDefault()
    const next = new URLSearchParams()
    if (actorUid) next.set('actor_uid', actorUid)
    if (eventType) next.set('event_type', eventType)
    if (targetKind) next.set('target_kind', targetKind)
    if (since) next.set('since', since)
    if (until) next.set('until', until)
    next.set('page', '1')
    setParams(next)
  }

  function setPage(p: number) {
    const next = new URLSearchParams(params)
    next.set('page', String(p))
    setParams(next)
  }

  function reset() {
    setActorUid('')
    setEventType('')
    setTargetKind('')
    setSince('')
    setUntil('')
    setParams(new URLSearchParams())
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="px-4 md:px-6 py-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('audit.title')}</h1>
        <Link to="/admin" className="text-primary underline text-sm">
          ← {t('audit.backToDashboard')}
        </Link>
      </div>

      <form
        onSubmit={applyFilters}
        className="rounded-xl border border-border bg-surface-raised p-4 grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-6 gap-3"
      >
        <input
          type="text"
          placeholder={t('audit.filters.actorUid')}
          value={actorUid}
          onChange={(e) => setActorUid(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        />
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        >
          <option value="">{t('audit.filters.anyEvent')}</option>
          {eventTypes.map((e) => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder={t('audit.filters.targetKind')}
          value={targetKind}
          onChange={(e) => setTargetKind(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        />
        <input
          type="date"
          value={since}
          onChange={(e) => setSince(e.target.value)}
          aria-label={t('audit.filters.since')}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        />
        <input
          type="date"
          value={until}
          onChange={(e) => setUntil(e.target.value)}
          aria-label={t('audit.filters.until')}
          className="px-3 py-2 rounded-lg border border-border bg-surface"
        />
        <div className="flex gap-2">
          <button type="submit"
                  className="px-3 py-2 rounded-lg bg-primary text-on-primary text-sm flex-1">
            {t('audit.filters.apply')}
          </button>
          <button type="button" onClick={reset}
                  className="px-3 py-2 rounded-lg border border-border text-sm">
            {t('audit.filters.reset')}
          </button>
        </div>
      </form>

      {error && <p className="text-danger text-sm">{error}</p>}

      {data === null && !error && (
        <p className="text-muted-fg">{t('common.loading')}</p>
      )}

      {data !== null && data.items.length === 0 && (
        <p className="text-muted-fg">{t('audit.empty')}</p>
      )}

      {data !== null && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-raised">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-border bg-surface">
                <th className="px-4 py-2">{t('audit.table.when')}</th>
                <th className="px-4 py-2">{t('audit.table.event')}</th>
                <th className="px-4 py-2">{t('audit.table.actor')}</th>
                <th className="px-4 py-2">{t('audit.table.target')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 text-muted-fg whitespace-nowrap">
                    {row.created_at?.replace('T', ' ').slice(0, 19) ?? '—'}
                  </td>
                  <td className="px-4 py-2 font-mono">{row.event_type}</td>
                  <td className="px-4 py-2">{row.actor_uid}</td>
                  <td className="px-4 py-2 text-muted-fg">
                    {row.target_kind}/{row.target_id}
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
          onPrev={() => setPage(Math.max(1, page - 1))}
          onNext={() => setPage(Math.min(totalPages, page + 1))}
        />
      )}
    </div>
  )
}
