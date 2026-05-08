import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import GroupJoinCTA from '../../components/GroupJoinCTA'
import { useAuth } from '../../contexts/AuthContext'
import { ApiError } from '../../lib/apiError'
import { startLink, unlinkTelegram } from '../../lib/link'

/**
 * `/settings/link-telegram` (US-M12.3).
 *
 * Two states driven by the auth profile:
 *  - **Not linked** (`profile.id` starts with `web_`): show 3-step
 *    instructions, a primary "Open Telegram bot" CTA that mints a
 *    web→TG token via `POST /api/v1/link/start` and opens the bot
 *    deep-link, plus the optional Group CTA.
 *  - **Linked** (`profile.id` is a numeric Telegram id): show the
 *    connected state and an "Unlink Telegram" button gated by a
 *    confirm modal.
 */
export default function LinkTelegramPage() {
  const { t } = useTranslation('link')
  const navigate = useNavigate()
  const { user, loading, profile, refreshProfile } = useAuth()

  if (loading) {
    return null
  }
  if (!profile) {
    // Post-unlink: the row's auth_uid was just cleared, so /me 404s
    // until the dashboard auto-create runs. Redirect there so the
    // user lands on a working page instead of a blank screen.
    if (user) {
      return (
        <main className="max-w-md mx-auto px-4 py-12 text-center">
          <p className="text-sm text-muted-fg">
            {t('settings.heading')}…
          </p>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {t('redeem.success.linked.cta')}
          </button>
        </main>
      )
    }
    return null
  }

  const isLinked = !profile.id.startsWith('web_')
  return (
    <main className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <div className="mb-4 text-sm">
        <Link to="/settings" className="text-primary underline">
          ← {t('settings.heading', 'Settings')}
        </Link>
      </div>
      <h1 className="text-2xl font-semibold text-fg">{t('settings.heading')}</h1>
      <div className="mt-6">
        {isLinked ? (
          <LinkedState
            onChanged={async () => {
              await refreshProfile()
              // Post-unlink the row has no auth_uid, so /me 404s and
              // the profile is null. Dashboard's auto-create rebuilds
              // a fresh web_xxx — bounce there so the user sees a
              // working page instead of this one going blank.
              navigate('/')
            }}
          />
        ) : (
          <NotLinkedState />
        )}
      </div>
      <div className="mt-6">
        <GroupJoinCTA />
      </div>
    </main>
  )
}

// ── Not-linked state ──────────────────────────────────────────────────

function NotLinkedState() {
  const { t } = useTranslation('link')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const open = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const res = await startLink()
      window.location.href = res.bot_deep_link
    } catch (e) {
      const message = e instanceof ApiError ? e.localize() : (e as Error).message
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-2xl border border-border/60 bg-surface-raised p-5">
      <h2 className="font-semibold text-fg">
        {t('settings.notLinked.stepsTitle')}
      </h2>
      <ol className="mt-3 space-y-2 text-sm text-muted-fg list-decimal list-inside">
        <li>{t('settings.notLinked.step1')}</li>
        <li>{t('settings.notLinked.step2')}</li>
        <li>{t('settings.notLinked.step3')}</li>
      </ol>
      <button
        type="button"
        onClick={open}
        disabled={busy}
        className="mt-5 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {busy
          ? t('settings.notLinked.creatingToken')
          : t('settings.notLinked.openBotCta')}
      </button>
      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger"
        >
          <p className="font-medium">{t('settings.notLinked.errorTitle')}</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : null}
    </section>
  )
}

// ── Linked state + unlink confirm ─────────────────────────────────────

function LinkedState({ onChanged }: { onChanged: () => Promise<void> }) {
  const { t } = useTranslation('link')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const doUnlink = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await unlinkTelegram()
      await onChanged()
      setConfirmOpen(false)
    } catch (e) {
      const message = e instanceof ApiError ? e.localize() : (e as Error).message
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-2xl border border-border/60 bg-surface-raised p-5">
      <h2 className="font-semibold text-fg">{t('settings.linked.title')}</h2>
      <p className="text-sm text-muted-fg mt-1">
        {t('settings.linked.description')}
      </p>
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        className="mt-4 inline-flex items-center justify-center rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-fg hover:bg-surface-raised"
      >
        {t('settings.linked.unlinkCta')}
      </button>
      {confirmOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="unlink-confirm-title"
          className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 px-4"
        >
          <div className="max-w-sm w-full bg-surface-raised rounded-2xl p-5 shadow-lg">
            <h3
              id="unlink-confirm-title"
              className="font-semibold text-fg"
            >
              {t('settings.linked.unlinkConfirmTitle')}
            </h3>
            <p className="text-sm text-muted-fg mt-2">
              {t('settings.linked.unlinkConfirmBody')}
            </p>
            {error ? (
              <div
                role="alert"
                className="mt-3 rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger"
              >
                <p className="font-medium">
                  {t('settings.linked.unlinkErrorTitle')}
                </p>
                <p className="mt-1">{error}</p>
              </div>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                disabled={busy}
                className="inline-flex items-center justify-center rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg hover:bg-surface-raised disabled:opacity-50"
              >
                {t('settings.linked.unlinkCancel')}
              </button>
              <button
                type="button"
                onClick={doUnlink}
                disabled={busy}
                className="inline-flex items-center justify-center rounded-md bg-danger px-3 py-1.5 text-sm font-medium text-danger-foreground hover:bg-danger/90 disabled:opacity-50"
              >
                {t('settings.linked.unlinkConfirm')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
