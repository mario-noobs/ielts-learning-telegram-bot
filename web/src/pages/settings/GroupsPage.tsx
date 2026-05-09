/**
 * /settings/groups — list groups the user is a member of (US-#227).
 *
 * Web alternative to the bot's `/groupsettings` command, which forces
 * the user back into the group chat to edit. Empty state nudges
 * web-only users to link Telegram first.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { useProfile } from '../../contexts/AuthContext'
import { apiFetch } from '../../lib/api'

interface GroupSummary {
  id: string
  name: string | null
  member_count: number
  role: 'owner' | 'member'
  default_band: number
  topics: string[]
  daily_time: string | null
}

export default function GroupsPage() {
  const { t } = useTranslation(['settings', 'common'])
  const profile = useProfile()
  const [groups, setGroups] = useState<GroupSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // `web_*` ids are users who haven't redeemed a Telegram link yet —
  // they can't be in any group, so the empty state nudges them to link.
  // A linked user who legitimately has zero groups gets different copy
  // (no "Link Telegram" CTA, since they're already linked) so we
  // don't bounce them to a page that says "you're already linked".
  const isLinked = !!profile && profile.id && !profile.id.startsWith('web_')

  useEffect(() => {
    apiFetch<GroupSummary[]>('/api/v1/me/groups')
      .then(setGroups)
      .catch((e) => setError((e as Error).message))
  }, [])

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <div>
        <Link
          to="/settings"
          className="text-sm text-muted-fg hover:text-fg inline-flex items-center gap-1"
        >
          <Icon name="ArrowLeft" size="sm" /> {t('common:actions.back')}
        </Link>
      </div>
      <h1 className="text-2xl font-bold text-fg">
        {t('groups.heading')}
      </h1>
      <p className="text-sm text-muted-fg">{t('groups.subheading')}</p>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {!groups && !error && (
        <p className="text-muted-fg">{t('common:status.loading')}</p>
      )}

      {groups && groups.length === 0 && (
        <section className="rounded-xl border border-dashed border-border p-6 text-center">
          {isLinked ? (
            <>
              <h2 className="font-semibold text-fg">
                {t('groups.emptyLinked.heading')}
              </h2>
              <p className="mt-2 text-sm text-muted-fg">
                {t('groups.emptyLinked.description')}
              </p>
            </>
          ) : (
            <>
              <h2 className="font-semibold text-fg">
                {t('groups.empty.heading')}
              </h2>
              <p className="mt-2 text-sm text-muted-fg">
                {t('groups.empty.description')}
              </p>
              <Link
                to="/settings/link-telegram"
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-fg hover:bg-primary-hover"
              >
                {t('groups.empty.cta')}
              </Link>
            </>
          )}
        </section>
      )}

      {groups && groups.length > 0 && (
        <ul className="space-y-3">
          {groups.map((g) => (
            <li key={g.id}>
              <Link
                to={`/settings/groups/${g.id}`}
                className="block rounded-xl border border-border bg-surface-raised p-4 hover:border-primary/40 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h2 className="font-semibold text-fg">
                      {g.name || t('groups.card.unnamed', { id: g.id })}
                    </h2>
                    <p className="mt-1 text-xs text-muted-fg">
                      {t('groups.card.memberCount', { count: g.member_count })}
                      {g.daily_time && ` · ${t('groups.card.dailyTime', { time: g.daily_time })}`}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                        {t('groups.card.band', { band: g.default_band.toFixed(1) })}
                      </span>
                      {g.topics.slice(0, 3).map((tp) => (
                        <span
                          key={tp}
                          className="inline-flex items-center rounded-full bg-surface px-2 py-0.5 text-xs text-muted-fg"
                        >
                          {tp}
                        </span>
                      ))}
                      {g.topics.length > 3 && (
                        <span className="text-xs text-muted-fg">
                          +{g.topics.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                  <span
                    className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
                      g.role === 'owner'
                        ? 'bg-success/10 text-success'
                        : 'bg-muted-fg/10 text-muted-fg'
                    }`}
                  >
                    {t(`groups.role.${g.role}`)}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
