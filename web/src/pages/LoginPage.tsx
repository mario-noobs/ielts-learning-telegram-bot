import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useSearchParams } from 'react-router-dom'
import LoadingScreen from '../components/LoadingScreen'
import LogoMark from '../components/brand/LogoMark'
import { useAuth, type LocalRegisterData } from '../contexts/AuthContext'
import { localizeError } from '../lib/apiError'
import { externalBrowserUrl, isInAppBrowser, shouldUseRedirectAuth } from '../lib/browser'

type Mode = 'options' | 'login' | 'register'

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="currentColor" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
      <path fill="currentColor" opacity=".8" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
      <path fill="currentColor" opacity=".6" d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/>
      <path fill="currentColor" opacity=".73" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z"/>
    </svg>
  )
}

function EmailIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="4" width="20" height="16" rx="2"/>
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
    </svg>
  )
}

function strengthScore(pw: string): 0 | 1 | 2 | 3 | 4 {
  if (!pw) return 0
  let s = 0
  if (pw.length >= 8) s++
  if (pw.length >= 12) s++
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++
  if (/[0-9]/.test(pw)) s++
  if (/[^A-Za-z0-9]/.test(pw)) s++
  return Math.min(4, s) as 0 | 1 | 2 | 3 | 4
}

const STRENGTH_LABEL = ['', 'Weak', 'Fair', 'Good', 'Strong'] as const
const STRENGTH_COLOR = [
  '',
  'bg-red-500',
  'bg-amber-400',
  'bg-blue-400',
  'bg-success',
] as const

export default function LoginPage() {
  const { t } = useTranslation('common')
  const { user, profile, loading, signInWithGoogle, signInLocal, registerLocal } = useAuth()
  const [searchParams] = useSearchParams()

  const [mode, setMode] = useState<Mode>('options')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const inAppBrowser = isInAppBrowser()
  const redirectGoogleAuth = shouldUseRedirectAuth()
  const currentHref = typeof window === 'undefined' ? '' : window.location.href
  const browserHref = currentHref ? externalBrowserUrl(currentHref) : null
  const [showPw, setShowPw] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [showOptional, setShowOptional] = useState(false)
  const [copied, setCopied] = useState(false)

  const [loginFields, setLoginFields] = useState({ email: '', password: '' })
  const [regFields, setRegFields] = useState<LocalRegisterData & { confirm_password: string }>({
    email: '',
    username: '',
    password: '',
    confirm_password: '',
    phone: '',
    address: '',
  })

  const strength = strengthScore(regFields.password)

  if (loading) {
    return <LoadingScreen fullScreen />
  }
  const next = searchParams.get('next')
  const safeNext = next?.startsWith('/') && !next.startsWith('//') ? next : '/'
  if (user || profile) return <Navigate to={safeNext} replace />

  const clearError = () => setFormError(null)

  const handleLoginChange = (e: ChangeEvent<HTMLInputElement>) => {
    clearError()
    setLoginFields(f => ({ ...f, [e.target.name]: e.target.value }))
  }

  const handleRegChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    clearError()
    setRegFields(f => ({ ...f, [e.target.name]: e.target.value }))
  }

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setFormError(null)
    try {
      await signInLocal(loginFields.email, loginFields.password)
    } catch (err) {
      setFormError(localizeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setFormError(null)
    try {
      await registerLocal({
        email: regFields.email,
        username: regFields.username,
        password: regFields.password,
        confirm_password: regFields.confirm_password,
        phone: regFields.phone || undefined,
        address: regFields.address || undefined,
      })
    } catch (err) {
      setFormError(localizeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setSubmitting(true)
    setFormError(null)
    try {
      await signInWithGoogle({ redirect: redirectGoogleAuth })
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? ''
      if (code === 'auth/disallowed-useragent' || code === 'auth/operation-not-supported-in-this-environment') {
        setFormError(t('auth.inAppBrowserWarning') + ' ' + t('auth.inAppBrowserHint'))
      } else {
        setFormError(localizeError(err))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleOpenBrowser = () => {
    if (!browserHref) return
    window.location.href = browserHref
  }

  const handleCopyLink = async () => {
    if (!currentHref) return
    try {
      await navigator.clipboard.writeText(currentHref)
      setCopied(true)
    } catch {
      setFormError(t('auth.copyLinkFailed'))
    }
  }

  const inputCls =
    'w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-fg placeholder:text-muted-fg focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:opacity-50'

  const labelCls = 'mb-1 block text-xs font-medium text-fg'

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-5">
      {/* Visual side */}
      <aside
        aria-hidden="true"
        className="relative col-span-1 flex items-end overflow-hidden bg-gradient-to-br from-primary/15 via-primary/5 to-bg p-8 lg:col-span-3 lg:p-12"
      >
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-8 top-12 h-32 w-44 rotate-[-6deg] rounded-2xl border border-border bg-surface-raised p-4 shadow-md">
            <div className="mb-2 h-2 w-20 rounded-full bg-primary" />
            <div className="mb-1.5 h-1.5 w-32 rounded-full bg-muted-fg/40" />
            <div className="mb-1.5 h-1.5 w-24 rounded-full bg-muted-fg/40" />
            <div className="h-1.5 w-16 rounded-full bg-muted-fg/40" />
          </div>
          <div className="absolute right-12 top-32 h-28 w-40 rotate-[5deg] rounded-2xl border border-border bg-surface-raised p-4 shadow-md">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
              ✓ Band 7.5
            </div>
            <div className="mb-1.5 h-1.5 w-28 rounded-full bg-muted-fg/40" />
            <div className="h-1.5 w-20 rounded-full bg-muted-fg/40" />
          </div>
          <div className="absolute bottom-32 right-20 hidden h-24 w-36 rotate-[-3deg] rounded-2xl border border-border bg-surface-raised p-4 shadow-md md:block">
            <div className="mb-2 h-2 w-24 rounded-full bg-accent" />
            <div className="mb-1 h-1.5 w-28 rounded-full bg-muted-fg/40" />
            <div className="h-1.5 w-20 rounded-full bg-muted-fg/40" />
          </div>
        </div>
        <div className="relative z-10 max-w-lg">
          <div className="mb-6 flex items-center gap-3">
            <LogoMark size="lg" />
            <span className="text-2xl font-bold text-fg">{t('brand.name')}</span>
          </div>
          <h1 className="mb-3 text-3xl font-bold text-fg lg:text-4xl">{t('auth.heroTitle')}</h1>
          <p className="mb-6 text-base text-muted-fg lg:text-lg">{t('auth.heroSubtitle')}</p>
          <ul className="space-y-2 text-sm text-fg">
            {(['bullet1', 'bullet2', 'bullet3'] as const).map(k => (
              <li key={k} className="flex items-start gap-2">
                <span aria-hidden="true" className="text-primary">✓</span>
                {t(`auth.${k}`)}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Form side */}
      <main className="col-span-1 flex items-center justify-center bg-bg px-6 py-12 lg:col-span-2 lg:px-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <LogoMark size="md" />
              <span className="text-xl font-bold text-fg">{t('brand.name')}</span>
            </div>
          </div>

          {inAppBrowser && (
            <>
              <h2 className="mb-2 text-2xl font-bold text-fg">{t('auth.openInBrowserTitle')}</h2>
              <p className="mb-6 text-sm text-muted-fg">{t('auth.openInBrowserBody')}</p>

              <div className="mb-5 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                <p className="font-medium">{t('auth.inAppBrowserWarning')}</p>
                <p className="mt-1 opacity-80">{t('auth.inAppBrowserHint')}</p>
              </div>

              {browserHref && (
                <button
                  type="button"
                  onClick={handleOpenBrowser}
                  className="flex w-full items-center justify-center rounded-lg bg-primary px-6 py-3 font-medium text-on-primary transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {t('auth.openInChrome')}
                </button>
              )}

              <button
                type="button"
                onClick={handleCopyLink}
                className={`${browserHref ? 'mt-3' : ''} flex w-full items-center justify-center rounded-lg border border-border bg-bg px-6 py-3 font-medium text-fg transition hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`}
              >
                {copied ? t('auth.linkCopied') : t('auth.copyLoginLink')}
              </button>

              <p className="mt-4 text-center text-xs text-muted-fg">
                {t('auth.openBrowserManualHint')}
              </p>

              {formError && (
                <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">
                  {formError}
                </p>
              )}
            </>
          )}

          {/* Options view */}
          {!inAppBrowser && mode === 'options' && (
            <>
              <h2 className="mb-2 text-2xl font-bold text-fg">{t('auth.welcomeBack')}</h2>
              <p className="mb-6 text-sm text-muted-fg">{t('auth.tagline')}</p>

              <button
                onClick={handleGoogleSignIn}
                disabled={submitting}
                className="flex w-full items-center justify-center gap-3 rounded-lg bg-primary px-6 py-3 font-medium text-on-primary transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <GoogleIcon />
                {t('nav.signInWithGoogle')}
              </button>

              <div className="my-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs text-muted-fg">{t('auth.orDivider')}</span>
                <div className="h-px flex-1 bg-border" />
              </div>

              <button
                onClick={() => setMode('login')}
                className="flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-bg px-6 py-3 font-medium text-fg transition hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <EmailIcon />
                {t('auth.signInWithEmail')}
              </button>

              <p className="mt-4 text-center text-xs text-muted-fg">
                {t('auth.dontHaveAccount')}{' '}
                <button
                  onClick={() => setMode('register')}
                  className="font-medium text-primary hover:underline"
                >
                  {t('auth.signUpLink')}
                </button>
              </p>
            </>
          )}

          {/* Login view */}
          {!inAppBrowser && mode === 'login' && (
            <>
              <h2 className="mb-2 text-2xl font-bold text-fg">{t('auth.signIn')}</h2>
              <p className="mb-6 text-sm text-muted-fg">{t('auth.tagline')}</p>

              <form onSubmit={handleLogin} noValidate className="space-y-4">
                <div>
                  <label htmlFor="login-email" className={labelCls}>{t('auth.email')}</label>
                  <input
                    id="login-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={loginFields.email}
                    onChange={handleLoginChange}
                    className={inputCls}
                    placeholder="you@example.com"
                  />
                </div>

                <div>
                  <label htmlFor="login-password" className={labelCls}>{t('auth.password')}</label>
                  <div className="relative">
                    <input
                      id="login-password"
                      name="password"
                      type={showPw ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={loginFields.password}
                      onChange={handleLoginChange}
                      className={`${inputCls} pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw(v => !v)}
                      className="absolute inset-y-0 right-3 flex items-center text-muted-fg hover:text-fg"
                      aria-label={showPw ? t('auth.hidePassword') : t('auth.showPassword')}
                    >
                      {showPw ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                  <div className="mt-1 flex justify-end">
                    <button
                      type="button"
                      disabled
                      title={t('auth.forgotPasswordDisabledTooltip')}
                      className="cursor-not-allowed text-xs text-muted-fg/50"
                    >
                      {t('auth.forgotPassword')}
                    </button>
                  </div>
                </div>

                {formError && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">
                    {formError}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="flex w-full items-center justify-center rounded-lg bg-primary px-6 py-3 font-medium text-on-primary transition hover:bg-primary/90 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {submitting ? t('status.loading') : t('auth.signIn')}
                </button>
              </form>

              <div className="mt-5 flex flex-col items-center gap-2">
                <p className="text-xs text-muted-fg">
                  {t('auth.dontHaveAccount')}{' '}
                  <button onClick={() => { setMode('register'); clearError() }} className="font-medium text-primary hover:underline">
                    {t('auth.signUpLink')}
                  </button>
                </p>
                <button
                  onClick={() => { setMode('options'); clearError() }}
                  className="text-xs text-muted-fg hover:text-fg"
                >
                  {t('auth.useGoogleInstead')}
                </button>
              </div>
            </>
          )}

          {/* Register view */}
          {!inAppBrowser && mode === 'register' && (
            <>
              <h2 className="mb-2 text-2xl font-bold text-fg">{t('auth.createAccount')}</h2>
              <p className="mb-6 text-sm text-muted-fg">{t('auth.tagline')}</p>

              <form onSubmit={handleRegister} noValidate className="space-y-4">
                <div>
                  <label htmlFor="reg-email" className={labelCls}>{t('auth.email')}</label>
                  <input
                    id="reg-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={regFields.email}
                    onChange={handleRegChange}
                    className={inputCls}
                    placeholder="you@example.com"
                  />
                </div>

                <div>
                  <label htmlFor="reg-password" className={labelCls}>{t('auth.password')}</label>
                  <div className="relative">
                    <input
                      id="reg-password"
                      name="password"
                      type={showPw ? 'text' : 'password'}
                      autoComplete="new-password"
                      required
                      value={regFields.password}
                      onChange={handleRegChange}
                      className={`${inputCls} pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw(v => !v)}
                      className="absolute inset-y-0 right-3 flex items-center text-muted-fg hover:text-fg"
                      aria-label={showPw ? t('auth.hidePassword') : t('auth.showPassword')}
                    >
                      {showPw ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                  {regFields.password && (
                    <div className="mt-2">
                      <div className="flex gap-1">
                        {[1, 2, 3, 4].map(i => (
                          <div
                            key={i}
                            className={`h-1 flex-1 rounded-full transition-all ${strength >= i ? STRENGTH_COLOR[strength] : 'bg-border'}`}
                          />
                        ))}
                      </div>
                      <p className="mt-1 text-xs text-muted-fg">{STRENGTH_LABEL[strength]}</p>
                    </div>
                  )}
                </div>

                <div>
                  <label htmlFor="reg-confirm" className={labelCls}>{t('auth.confirmPassword')}</label>
                  <div className="relative">
                    <input
                      id="reg-confirm"
                      name="confirm_password"
                      type={showConfirm ? 'text' : 'password'}
                      autoComplete="new-password"
                      required
                      value={regFields.confirm_password}
                      onChange={handleRegChange}
                      className={`${inputCls} pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm(v => !v)}
                      className="absolute inset-y-0 right-3 flex items-center text-muted-fg hover:text-fg"
                      aria-label={showConfirm ? t('auth.hidePassword') : t('auth.showPassword')}
                    >
                      {showConfirm ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="reg-username" className={labelCls}>{t('auth.username')}</label>
                  <input
                    id="reg-username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    required
                    value={regFields.username}
                    onChange={handleRegChange}
                    className={inputCls}
                    placeholder="yourname"
                  />
                </div>

                {/* Optional details */}
                <button
                  type="button"
                  onClick={() => setShowOptional(v => !v)}
                  className="flex w-full items-center justify-between text-xs font-medium text-muted-fg hover:text-fg"
                >
                  <span>{t('auth.optionalDetails')}</span>
                  <svg
                    className={`h-4 w-4 transition-transform ${showOptional ? 'rotate-180' : ''}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {showOptional && (
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="reg-phone" className={labelCls}>
                        {t('auth.phone')}{' '}
                        <span className="font-normal text-muted-fg">{t('auth.optional')}</span>
                      </label>
                      <input
                        id="reg-phone"
                        name="phone"
                        type="tel"
                        inputMode="tel"
                        autoComplete="tel"
                        value={regFields.phone}
                        onChange={handleRegChange}
                        className={inputCls}
                        placeholder="+84 xxx xxx xxx"
                      />
                    </div>
                    <div>
                      <label htmlFor="reg-address" className={labelCls}>
                        {t('auth.address')}{' '}
                        <span className="font-normal text-muted-fg">{t('auth.optional')}</span>
                      </label>
                      <input
                        id="reg-address"
                        name="address"
                        type="text"
                        autoComplete="street-address"
                        value={regFields.address}
                        onChange={handleRegChange}
                        className={inputCls}
                      />
                    </div>
                  </div>
                )}

                {formError && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">
                    {formError}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="flex w-full items-center justify-center rounded-lg bg-primary px-6 py-3 font-medium text-on-primary transition hover:bg-primary/90 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {submitting ? t('status.loading') : t('auth.createAccount')}
                </button>
              </form>

              <div className="mt-5 flex flex-col items-center gap-2">
                <p className="text-xs text-muted-fg">
                  {t('auth.alreadyHaveAccount')}{' '}
                  <button onClick={() => { setMode('login'); clearError() }} className="font-medium text-primary hover:underline">
                    {t('auth.signInLink')}
                  </button>
                </p>
                <button
                  onClick={() => { setMode('options'); clearError() }}
                  className="text-xs text-muted-fg hover:text-fg"
                >
                  {t('auth.useGoogleInstead')}
                </button>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
