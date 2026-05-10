/**
 * Telegram-onboarding tracker (#242 round 2).
 *
 * A persistent dashboard widget that ticks off as the user completes
 * each step. Auto-hides once both are done — no dismiss button, since
 * the previous "X" iteration confused users into thinking the guide
 * was gone forever.
 *
 * Steps:
 *   1. Link Telegram (profile.id stops being a `web_<hex>` placeholder)
 *   2. Use with a group (GET /api/v1/me/groups returns at least one row)
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { useAuth } from '../../contexts/AuthContext'
import { apiFetch } from '../../lib/api'

interface GroupSummary {
  id: string
}

export default function TelegramOnboarding() {
  const { t } = useTranslation('dashboard')
  const { profile } = useAuth()
  const [groupCount, setGroupCount] = useState<number | null>(null)

  const isLinked = profile != null && !profile.id.startsWith('web_')
  const hasGroup = groupCount != null && groupCount > 0
  const bothDone = isLinked && hasGroup

  useEffect(() => {
    // Only fetch the groups list if the user is linked. Web-placeholder
    // accounts never have groups, so the call would 404/return empty.
    if (!isLinked) {
      setGroupCount(0)
      return
    }
    let cancelled = false
    apiFetch<GroupSummary[]>('/api/v1/me/groups')
      .then((rows) => {
        if (!cancelled) setGroupCount(Array.isArray(rows) ? rows.length : 0)
      })
      .catch(() => {
        if (!cancelled) setGroupCount(0)
      })
    return () => {
      cancelled = true
    }
  }, [isLinked])

  const progress = useMemo(() => {
    let done = 0
    if (isLinked) done += 1
    if (hasGroup) done += 1
    return done
  }, [isLinked, hasGroup])

  // Auto-hide once both steps are done.
  if (!profile || bothDone) return null

  return (
    <section
      aria-labelledby="telegram-onboarding-heading"
      className="rounded-2xl border border-primary/20 bg-primary/5 p-4"
    >
      <header>
        <h2
          id="telegram-onboarding-heading"
          className="text-base font-semibold text-fg"
        >
          {t('telegramOnboarding.heading')}
        </h2>
        <p className="text-xs text-muted-fg mt-0.5">
          {t('telegramOnboarding.subheading')}
        </p>
      </header>

      <div className="mt-3">
        <div
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={2}
          className="h-1.5 w-full overflow-hidden rounded-full bg-surface"
        >
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${(progress / 2) * 100}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-muted-fg">
          {t('telegramOnboarding.progress', { done: progress, total: 2 })}
        </p>
      </div>

      <ol className="mt-4 space-y-2">
        <Step
          done={isLinked}
          title={t('telegramOnboarding.step1.title')}
          description={t('telegramOnboarding.step1.description')}
          ctaLabel={t('telegramOnboarding.step1.cta')}
          ctaHref="/settings/link-telegram"
        />
        <Step
          done={hasGroup}
          // Step 2 is only actionable once step 1 is done — surface it as
          // disabled-tone otherwise so the order is obvious.
          dimmed={!isLinked}
          title={t('telegramOnboarding.step2.title')}
          description={t('telegramOnboarding.step2.description')}
          ctaLabel={t('telegramOnboarding.step2.cta')}
          ctaHref="/settings/link-telegram"
        />
      </ol>
    </section>
  )
}

function Step({
  done,
  dimmed,
  title,
  description,
  ctaLabel,
  ctaHref,
}: {
  done: boolean
  dimmed?: boolean
  title: string
  description: string
  ctaLabel: string
  ctaHref: string
}) {
  return (
    <li
      className={`flex items-start gap-3 rounded-lg border border-border bg-surface p-3 ${
        dimmed ? 'opacity-60' : ''
      }`}
    >
      <Icon
        name={done ? 'CheckCircle2' : 'Circle'}
        size="md"
        className={done ? 'text-success' : 'text-muted-fg'}
      />
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium text-fg ${done ? 'line-through opacity-70' : ''}`}>
          {title}
        </p>
        <p className="text-xs text-muted-fg mt-0.5">{description}</p>
        {!done && !dimmed ? (
          <Link
            to={ctaHref}
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            {ctaLabel} →
          </Link>
        ) : null}
      </div>
    </li>
  )
}
