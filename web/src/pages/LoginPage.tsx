import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import LogoMark from '../components/brand/LogoMark'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { t } = useTranslation('common')
  const { user, loading, signInWithGoogle } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-fg">
        {t('status.loading')}
      </div>
    )
  }
  if (user) return <Navigate to="/" replace />

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-5">
      {/* Visual side — desktop ≥lg, top on mobile */}
      <aside
        aria-hidden="true"
        className="relative col-span-1 flex items-end overflow-hidden bg-gradient-to-br from-primary/15 via-primary/5 to-bg p-8 lg:col-span-3 lg:p-12"
      >
        {/* Floating decorative cards */}
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
            <span className="text-2xl font-bold text-fg">
              {t('brand.name')}
            </span>
          </div>
          <h1 className="mb-3 text-3xl font-bold text-fg lg:text-4xl">
            {t('auth.heroTitle')}
          </h1>
          <p className="mb-6 text-base text-muted-fg lg:text-lg">
            {t('auth.heroSubtitle')}
          </p>
          <ul className="space-y-2 text-sm text-fg">
            <li className="flex items-start gap-2">
              <span aria-hidden="true" className="text-primary">
                ✓
              </span>
              {t('auth.bullet1')}
            </li>
            <li className="flex items-start gap-2">
              <span aria-hidden="true" className="text-primary">
                ✓
              </span>
              {t('auth.bullet2')}
            </li>
            <li className="flex items-start gap-2">
              <span aria-hidden="true" className="text-primary">
                ✓
              </span>
              {t('auth.bullet3')}
            </li>
          </ul>
        </div>
      </aside>

      {/* Form side */}
      <main className="col-span-1 flex items-center justify-center bg-bg px-6 py-12 lg:col-span-2 lg:px-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <LogoMark size="md" />
              <span className="text-xl font-bold text-fg">
                {t('brand.name')}
              </span>
            </div>
          </div>
          <h2 className="mb-2 text-2xl font-bold text-fg">
            {t('auth.welcomeBack')}
          </h2>
          <p className="mb-6 text-sm text-muted-fg">{t('auth.tagline')}</p>
          <button
            onClick={signInWithGoogle}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-medium text-on-primary transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {t('nav.signInWithGoogle')}
          </button>
        </div>
      </main>
    </div>
  )
}
