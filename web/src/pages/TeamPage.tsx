import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Icon, { IconName } from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

type TeamRole = 'owner' | 'admin' | 'member'

interface TeamSummary {
  id: string
  name: string
  owner_uid: string
  plan_id: string
  seat_limit: number
  member_count: number
  my_role: TeamRole | null
  created_at: string | null
}

interface TeamMemberSummary {
  user_id: string
  name: string
  email: string | null
  role: TeamRole
  joined_at: string | null
  is_current_user: boolean
}

interface TeamOverviewResponse {
  week_start: string
  weekly_active_members: number
  study_minutes: number
  words_reviewed: number
  words_mastered: number
  quiz_count: number
  member_count: number
  seat_limit: number
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

interface TeamMembersResponse {
  team: TeamSummary
  members: TeamMemberSummary[]
}

interface TeamMemberUpdateResponse {
  member: TeamMemberSummary
}

const ROLE_META: Record<TeamRole, { icon: IconName; className: string }> = {
  owner: {
    icon: 'Crown',
    className: 'border-warning/30 bg-warning/15 text-warning',
  },
  admin: {
    icon: 'ShieldCheck',
    className: 'border-primary/30 bg-primary/10 text-primary',
  },
  member: {
    icon: 'Users',
    className: 'border-border bg-surface text-muted-fg',
  },
}

function absoluteInviteUrl(path: string) {
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

function formatDate(value: string | null) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
    .format(new Date(value))
}

export default function TeamPage() {
  const { t } = useTranslation(['team', 'common'])
  const { refreshProfile } = useAuth()
  const [team, setTeam] = useState<TeamSummary | null>(null)
  const [members, setMembers] = useState<TeamMemberSummary[]>([])
  const [overview, setOverview] = useState<TeamOverviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [inviteLoading, setInviteLoading] = useState(false)
  const [memberAction, setMemberAction] = useState('')
  const [invite, setInvite] = useState<TeamInviteCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  const loadWorkspace = useCallback(async (teamId: string) => {
    setWorkspaceLoading(true)
    try {
      const [membersRes, overviewRes] = await Promise.all([
        apiFetch<TeamMembersResponse>(`/api/v1/teams/${encodeURIComponent(teamId)}/members`),
        apiFetch<TeamOverviewResponse>(`/api/v1/teams/${encodeURIComponent(teamId)}/overview`),
      ])
      setTeam(membersRes.team)
      setMembers(membersRes.members)
      setOverview(overviewRes)
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setWorkspaceLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const res = await apiFetch<TeamMeResponse>('/api/v1/teams/me')
        if (cancelled) return
        setTeam(res.team)
        if (res.team) await loadWorkspace(res.team.id)
      } catch (e) {
        if (!cancelled) setError(localizeError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [loadWorkspace])

  const fullInviteUrl = useMemo(
    () => (invite ? absoluteInviteUrl(invite.invite_url) : ''),
    [invite],
  )

  const canManageMembers = team?.my_role === 'owner' || team?.my_role === 'admin'
  const canChangeRoles = team?.my_role === 'owner'

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
      await Promise.all([refreshProfile(), loadWorkspace(res.team.id)])
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

  const updateRole = async (member: TeamMemberSummary, role: 'admin' | 'member') => {
    if (!team || member.role === role) return
    setMemberAction(member.user_id)
    setError('')
    try {
      const res = await apiFetch<TeamMemberUpdateResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(member.user_id)}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ role }),
        },
      )
      setMembers((items) => items.map((item) => (
        item.user_id === member.user_id ? res.member : item
      )))
      track('team_member_role_updated', { team_id: team.id, role })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setMemberAction('')
    }
  }

  const removeMember = async (member: TeamMemberSummary) => {
    if (!team) return
    const confirmed = window.confirm(t('members.removeConfirm', { name: member.name }))
    if (!confirmed) return
    setMemberAction(member.user_id)
    setError('')
    try {
      await apiFetch(
        `/api/v1/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(member.user_id)}`,
        { method: 'DELETE' },
      )
      await refreshProfile()
      if (member.is_current_user) {
        setTeam(null)
        setMembers([])
        setOverview(null)
      } else {
        await loadWorkspace(team.id)
      }
      track('team_member_removed', { team_id: team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setMemberAction('')
    }
  }

  const RoleBadge = ({ role }: { role: TeamRole }) => {
    const meta = ROLE_META[role]
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold ${meta.className}`}
      >
        <Icon name={meta.icon} size="sm" className="text-current" />
        {t(`roles.${role}`)}
      </span>
    )
  }

  const overviewStats = overview ? [
    {
      key: 'active',
      icon: 'Users' as IconName,
      label: t('overview.activeMembers'),
      value: String(overview.weekly_active_members),
    },
    {
      key: 'minutes',
      icon: 'Clock' as IconName,
      label: t('overview.studyMinutes'),
      value: String(overview.study_minutes),
    },
    {
      key: 'reviewed',
      icon: 'RotateCcw' as IconName,
      label: t('overview.wordsReviewed'),
      value: String(overview.words_reviewed),
    },
    {
      key: 'mastered',
      icon: 'Trophy' as IconName,
      label: t('overview.wordsMastered'),
      value: String(overview.words_mastered),
    },
    {
      key: 'quiz',
      icon: 'ClipboardCheck' as IconName,
      label: t('overview.quizCount'),
      value: String(overview.quiz_count),
    },
  ] : []
  const hasActivity = overviewStats.some((item) => Number(item.value) > 0)

  if (loading) {
    return <LoadingScreen className="mx-auto max-w-5xl p-4" />
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
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
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-fg">{t('workspace.roleLabel')}</span>
                  <RoleBadge role={team.my_role ?? 'member'} />
                </div>
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

          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-fg">{t('overview.title')}</h2>
                <p className="text-sm text-muted-fg">
                  {overview ? t('overview.weekStart', { date: formatDate(overview.week_start) }) : t('overview.loading')}
                </p>
              </div>
              {workspaceLoading && (
                <span className="inline-flex items-center gap-2 text-sm text-muted-fg">
                  <Icon name="Loader2" size="sm" className="animate-spin" />
                  {t('overview.loading')}
                </span>
              )}
            </div>

            {overview && (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  {overviewStats.map((item) => (
                    <div key={item.key} className="rounded-md border border-border bg-bg p-3">
                      <div className="flex items-center gap-2 text-xs font-medium text-muted-fg">
                        <Icon name={item.icon} size="sm" variant="muted" />
                        {item.label}
                      </div>
                      <p className="mt-2 text-2xl font-semibold text-fg">{item.value}</p>
                    </div>
                  ))}
                </div>
                {!hasActivity && (
                  <p className="mt-3 rounded-md border border-border bg-bg px-3 py-2 text-sm text-muted-fg">
                    {t('overview.empty')}
                  </p>
                )}
              </>
            )}
          </section>

          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-fg">{t('members.title')}</h2>
                <p className="mt-1 max-w-xl text-sm text-muted-fg">{t('members.description')}</p>
              </div>
              {(team.my_role === 'owner' || team.my_role === 'admin') && (
                <button
                  type="button"
                  onClick={createInvite}
                  disabled={inviteLoading}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-70"
                >
                  {inviteLoading && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
                  {inviteLoading ? t('invite.creating') : t('invite.create')}
                </button>
              )}
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

            <div className="mt-4 divide-y divide-border rounded-lg border border-border bg-bg">
              {members.map((member) => {
                const canRemove = canManageMembers
                  && member.role !== 'owner'
                  && (team.my_role === 'owner' || member.role === 'member')
                const busy = memberAction === member.user_id
                return (
                  <div key={member.user_id} className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-semibold text-fg">{member.name}</p>
                        {member.is_current_user && (
                          <span className="rounded-md bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
                            {t('members.you')}
                          </span>
                        )}
                        <RoleBadge role={member.role} />
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-fg">
                        {member.email || member.user_id}
                        {member.joined_at ? ` · ${t('members.joined', { date: formatDate(member.joined_at) })}` : ''}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {canChangeRoles && member.role !== 'owner' && (
                        <select
                          aria-label={t('members.roleActionLabel', { name: member.name })}
                          value={member.role}
                          disabled={busy}
                          onChange={(event) => updateRole(member, event.target.value as 'admin' | 'member')}
                          className="min-h-10 rounded-md border border-border bg-surface px-2 text-sm text-fg"
                        >
                          <option value="member">{t('roles.member')}</option>
                          <option value="admin">{t('roles.admin')}</option>
                        </select>
                      )}
                      {canRemove && (
                        <button
                          type="button"
                          onClick={() => removeMember(member)}
                          disabled={busy}
                          className="inline-flex min-h-10 items-center justify-center rounded-md border border-danger/30 px-3 py-2 text-sm font-medium text-danger hover:bg-danger/10 disabled:opacity-60"
                        >
                          {busy ? t('members.removing') : t('members.remove')}
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
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
