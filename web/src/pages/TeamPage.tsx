import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Icon from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

interface TeamSummary {
  id: string
  name: string
  owner_uid: string
  plan_id: string
  seat_limit: number
  member_count: number
  my_role: 'owner' | 'admin' | 'member' | null
  created_at: string | null
}

interface TeamMeResponse {
  team: TeamSummary | null
}

interface TeamCreateResponse {
  team: TeamSummary
}

interface TeamInviteCreateResponse {
  token: string
  invite_url: string
  expires_at: string
}

function absoluteInviteUrl(path: string) {
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

export default function TeamPage() {
  const { t } = useTranslation(['team', 'common'])
  const { refreshProfile } = useAuth()
  const [team, setTeam] = useState<TeamSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [inviteLoading, setInviteLoading] = useState(false)
  const [invite, setInvite] = useState<TeamInviteCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiFetch<TeamMeResponse>('/api/v1/teams/me')
      .then((res) => {
        if (!cancelled) setTeam(res.team)
      })
      .catch((e) => {
        if (!cancelled) setError(localizeError(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const fullInviteUrl = useMemo(
    () => (invite ? absoluteInviteUrl(invite.invite_url) : ''),
    [invite],
  )

  const createTeam = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setSubmitting(true)
    setError('')
    try {
      const res = await apiFetch<TeamCreateResponse>('/api/v1/teams', {
        method: 'POST',
        body: JSON.stringify({ name: trimmed }),
      })
      setTeam(res.team)
      await refreshProfile()
      track('team_created', { team_id: res.team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSubmitting(false)
    }
  }

  const createInvite = async () => {
    if (!team) return
    setInviteLoading(true)
    setError('')
    setCopied(false)
    try {
      const res = await apiFetch<TeamInviteCreateResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/invites`,
        {
          method: 'POST',
          body: JSON.stringify({ role: 'member' }),
        },
      )
      setInvite(res)
      track('team_invite_created', { team_id: team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setInviteLoading(false)
    }
  }

  const copyInvite = async () => {
    if (!fullInviteUrl) return
    await navigator.clipboard?.writeText(fullInviteUrl)
    setCopied(true)
  }

  if (loading) {
    return <LoadingScreen className="mx-auto max-w-4xl p-4" />
  }

  return (
    <div className="mx-auto max-w-4xl p-4">
      <header className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">
          {t('page.eyebrow')}
        </p>
        <h1 className="mt-2 text-2xl font-bold text-fg">{t('page.heading')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-fg">{t('page.subtitle')}</p>
      </header>

      {error && (
        <p className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {team ? (
        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-medium text-muted-fg">{t('workspace.title')}</p>
                <h2 className="mt-1 text-xl font-semibold text-fg">{team.name}</h2>
                <p className="mt-2 text-sm text-muted-fg">
                  {t('workspace.role', { role: team.my_role ?? 'member' })}
                </p>
              </div>
              <div className="inline-flex items-center gap-2 rounded-md bg-primary/10 px-3 py-2 text-sm font-medium text-primary">
                <Icon name="Users" size="sm" variant="primary" />
                {t('workspace.members', {
                  count: team.member_count,
                  limit: team.seat_limit,
                })}
              </div>
            </div>
            <p className="mt-4 text-sm text-muted-fg">{t('workspace.privacy')}</p>
          </section>

          {(team.my_role === 'owner' || team.my_role === 'admin') && (
            <section className="rounded-lg border border-border bg-surface-raised p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-fg">{t('invite.title')}</h2>
                  <p className="mt-1 max-w-xl text-sm text-muted-fg">{t('invite.description')}</p>
                </div>
                <button
                  type="button"
                  onClick={createInvite}
                  disabled={inviteLoading}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-70"
                >
                  {inviteLoading && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
                  {inviteLoading ? t('invite.creating') : t('invite.create')}
                </button>
              </div>

              {invite && (
                <div className="mt-4 rounded-lg border border-border bg-bg p-3">
                  <label className="text-xs font-medium text-muted-fg" htmlFor="team-invite-link">
                    {t('invite.linkLabel')}
                  </label>
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                    <input
                      id="team-invite-link"
                      readOnly
                      value={fullInviteUrl}
                      className="min-h-10 flex-1 rounded-md border border-border bg-surface px-3 text-sm text-fg"
                    />
                    <button
                      type="button"
                      onClick={copyInvite}
                      className="inline-flex min-h-10 items-center justify-center rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:bg-surface"
                    >
                      {copied ? t('invite.copied') : t('invite.copy')}
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      ) : (
        <section className="rounded-lg border border-border bg-surface-raised p-4">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-fg">{t('create.title')}</h2>
            <p className="mt-1 text-sm text-muted-fg">{t('create.description')}</p>
          </div>
          <form onSubmit={createTeam} className="space-y-3">
            <label className="block text-sm font-medium text-fg" htmlFor="team-name">
              {t('create.nameLabel')}
            </label>
            <input
              id="team-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t('create.namePlaceholder')}
              maxLength={120}
              className="min-h-11 w-full rounded-md border border-border bg-bg px-3 text-sm text-fg placeholder:text-muted-fg"
            />
            <p className="text-xs text-muted-fg">{t('create.limit')}</p>
            <button
              type="submit"
              disabled={submitting || !name.trim()}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
            >
              {submitting && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
              {submitting ? t('create.creating') : t('create.submit')}
            </button>
          </form>
        </section>
      )}
    </div>
  )
}
