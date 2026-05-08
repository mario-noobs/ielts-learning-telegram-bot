import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { useAuth } from '../contexts/AuthContext'
import { ApiError } from '../lib/apiError'
import { redeemLink, type LinkRedeemResponse } from '../lib/link'

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME ?? ''

type RedeemErrorKind = 'expired' | 'alreadyUsed' | 'invalid' | 'missingToken'

interface RedeemError {
  kind: RedeemErrorKind
}

/**
 * `/link?token=...` page (US-M12.3).
 *
 * Four states:
 *  1. Loading — token present, currently calling redeem.
 *  2. Sign-in required — token present but no Firebase session.
 *  3. Success — sub-cases linked / merged / already_linked.
 *  4. Error — missingToken | invalid | expired | alreadyUsed.
 */
export default function LinkRedeemPage() {
  const { t } = useTranslation('link')
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { user, loading, signInWithGoogle, refreshProfile } = useAuth()
  const token = params.get('token')

  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<LinkRedeemResponse | null>(null)
  const [error, setError] = useState<RedeemError | null>(null)

  // Drive the redeem call once the user is signed in and a token is present.
  useEffect(() => {
    if (!token) {
      setError({ kind: 'missingToken' })
      return
    }
    if (loading || !user || result || error || busy) return

    setBusy(true)
    redeemLink(token)
      .then(async (res) => {
        setResult(res)
        // /me identity changed under the hood — refresh the auth profile so the
        // app shell picks up the merged role/plan/team values.
        await refreshProfile()
      })
      .catch((e) => {
        if (e instanceof ApiError) {
          if (e.code === 'auth.link.token_expired') setError({ kind: 'expired' })
          else if (e.code === 'auth.link.token_already_used')
            setError({ kind: 'alreadyUsed' })
          else setError({ kind: 'invalid' })
        } else {
          setError({ kind: 'invalid' })
        }
      })
      .finally(() => setBusy(false))
  }, [token, user, loading, result, error, busy, refreshProfile])

  const openBot = () => {
    if (BOT_USERNAME) {
      window.location.href = `https://t.me/${BOT_USERNAME}`
    }
  }

  // ── State 1: loading ────────────────────────────────────────────────
  if (busy || (token && user && !result && !error)) {
    return <CenteredCard title={t('redeem.title')} body={t('redeem.loading')} />
  }

  // ── State 4 (subset): missing token ─────────────────────────────────
  if (error?.kind === 'missingToken') {
    return (
      <CenteredCard
        title={t('redeem.error.missingToken.title')}
        body={t('redeem.error.missingToken.description')}
        cta={
          BOT_USERNAME
            ? { label: t('redeem.error.missingToken.cta'), onClick: openBot }
            : undefined
        }
      />
    )
  }

  // ── State 2: sign-in required ───────────────────────────────────────
  if (!loading && !user && token) {
    return (
      <CenteredCard
        title={t('redeem.signInRequired.title')}
        body={t('redeem.signInRequired.description')}
        cta={{
          label: t('redeem.signInRequired.cta'),
          onClick: () => {
            void signInWithGoogle()
          },
        }}
      />
    )
  }

  // ── State 3: success ────────────────────────────────────────────────
  if (result) {
    if (result.status === 'linked') {
      return (
        <CenteredCard
          title={t('redeem.success.linked.title')}
          body={t('redeem.success.linked.description')}
          cta={{
            label: t('redeem.success.linked.cta'),
            onClick: () => navigate('/'),
          }}
        />
      )
    }
    if (result.status === 'merged') {
      const counts = result.counts ?? {
        vocab_merged: 0,
        vocab_dropped: 0,
        quiz_merged: 0,
        writing_merged: 0,
        daily_merged: 0,
        daily_skipped: 0,
      }
      return (
        <CenteredCard
          title={t('redeem.success.merged.title')}
          body={t('redeem.success.merged.description', {
            vocab: counts.vocab_merged,
            quiz: counts.quiz_merged,
          })}
          cta={{
            label: t('redeem.success.merged.cta'),
            onClick: () => navigate('/'),
          }}
        />
      )
    }
    return (
      <CenteredCard
        title={t('redeem.success.alreadyLinked.title')}
        body={t('redeem.success.alreadyLinked.description')}
        cta={{
          label: t('redeem.success.alreadyLinked.cta'),
          onClick: () => navigate('/'),
        }}
      />
    )
  }

  // ── State 4: token errors ───────────────────────────────────────────
  if (error) {
    const key = error.kind  // 'expired' | 'alreadyUsed' | 'invalid'
    return (
      <CenteredCard
        title={t(`redeem.error.${key}.title`)}
        body={t(`redeem.error.${key}.description`)}
        cta={
          BOT_USERNAME
            ? { label: t(`redeem.error.${key}.cta`), onClick: openBot }
            : undefined
        }
      />
    )
  }

  // Loading state while AuthContext determines the session.
  return <CenteredCard title={t('redeem.title')} body={t('redeem.loading')} />
}

interface CenteredCardProps {
  title: string
  body: string
  cta?: { label: string; onClick: () => void }
}

function CenteredCard({ title, body, cta }: CenteredCardProps) {
  return (
    <main
      role="main"
      className="min-h-screen flex items-center justify-center bg-surface px-4"
    >
      <section
        aria-labelledby="redeem-title"
        className="max-w-md w-full bg-surface-raised rounded-2xl shadow-md p-6 sm:p-8 text-center"
      >
        <h1
          id="redeem-title"
          className="text-xl sm:text-2xl font-semibold text-fg"
        >
          {title}
        </h1>
        <p className="text-sm text-muted-fg mt-3">{body}</p>
        {cta ? (
          <button
            type="button"
            onClick={cta.onClick}
            className="mt-6 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {cta.label}
          </button>
        ) : null}
      </section>
    </main>
  )
}
