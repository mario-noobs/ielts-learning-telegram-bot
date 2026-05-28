import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import LoadingScreen from '../components/LoadingScreen'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

interface TeamInvitePreviewResponse {
  team_id: string
  team_name: string
  expires_at: string
  member_count: number
  seat_limit: number
  already_member: boolean
}

interface TeamInviteAcceptResponse {
  team: {
    id: string
    name: string
    my_role: 'owner' | 'admin' | 'member' | null
  }
}

export default function TeamInvitePage() {
  const { t } = useTranslation(['team', 'common'])
  const { token = '' } = useParams<{ token: string }>()
  const { profile, loading: authLoading, refreshProfile } = useAuth()
  const navigate = useNavigate()
  const [preview, setPreview] = useState<TeamInvitePreviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [accepting, setAccepting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    apiFetch<TeamInvitePreviewResponse>(`/api/v1/teams/invites/${encodeURIComponent(token)}`)
      .then((res) => {
        if (!cancelled) setPreview(res)
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
  }, [token])

  const acceptInvite = async () => {
    setAccepting(true)
    setError('')
    try {
      const res = await apiFetch<TeamInviteAcceptResponse>(
        `/api/v1/teams/invites/${encodeURIComponent(token)}/accept`,
        { method: 'POST' },
      )
      setAccepted(true)
      await refreshProfile()
      track('team_invite_accepted', { team_id: res.team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setAccepting(false)
    }
  }

  if (loading || authLoading) {
    return <LoadingScreen className="mx-auto max-w-xl p-4" />
  }

  if (error && !preview) {
    return (
      <div className="mx-auto max-w-xl p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('common:status.error')}
          description={error}
          primaryAction={{ label: t('common:actions.goToDashboard'), to: '/' }}
        />
      </div>
    )
  }

  if (!preview) return null

  const loginTarget = `/login?next=${encodeURIComponent(`/team/invite/${token}`)}`

  return (
    <div className="mx-auto max-w-xl p-4">
      <section className="rounded-lg border border-border bg-surface-raised p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">
          {t('page.eyebrow')}
        </p>
        <h1 className="mt-2 text-2xl font-bold text-fg">
          {t('join.heading', { team: preview.team_name })}
        </h1>
        <p className="mt-1 text-sm text-muted-fg">
          {t('join.subtitle', {
            count: preview.member_count,
            limit: preview.seat_limit,
          })}
        </p>
        <p className="mt-4 rounded-md border border-border bg-bg p-3 text-sm text-muted-fg">
          {t('join.privacy')}
        </p>
        <p className="mt-2 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm text-muted-fg">
          {t('join.beta')}
        </p>

        {error && (
          <p className="mt-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          {accepted ? (
            <>
              <p className="w-full text-sm font-medium text-success">{t('join.success')}</p>
              <button
                type="button"
                onClick={() => navigate('/team')}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary"
              >
                {t('join.goTeam')}
              </button>
            </>
          ) : profile ? (
            <button
              type="button"
              onClick={acceptInvite}
              disabled={accepting}
              className="inline-flex min-h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-70"
            >
              {accepting ? t('join.accepting') : t('join.accept')}
            </button>
          ) : (
            <Link
              to={loginTarget}
              className="inline-flex min-h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90"
            >
              {t('join.signIn')}
            </Link>
          )}
        </div>
      </section>
    </div>
  )
}
