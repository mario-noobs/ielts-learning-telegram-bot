import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { Badge, Button } from '../../components/ui'
import LanguageSwitcher from '../../components/LanguageSwitcher'
import { track } from '../../lib/analytics'

const SOCIAL_PROOF_COUNT = 2000

export default function Hero() {
  const { t } = useTranslation(['landing', 'common'])
  const { signInWithGoogle } = useAuth()

  const handleSignup = async () => {
    track('landing_cta_clicked', { cta: 'signup' })
    try {
      await signInWithGoogle()
    } catch {
      /* popup closed / network — silent; user retries */
    }
  }

  const handleDemo = () => {
    track('landing_cta_clicked', { cta: 'demo' })
  }

  return (
    <>
      <nav
        aria-label={t('landing:nav.ariaLabel')}
        className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 md:px-6"
      >
        <Link to="/" className="flex items-center gap-2 text-lg font-bold text-fg">
          {t('common:brand.name')}
          <Badge variant="primary" aria-label={t('common:auth.brandBetaLabel')}>
            {t('common:brand.beta')}
          </Badge>
        </Link>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <Link
            to="/login"
            className="rounded-xl px-3 py-2 text-sm font-medium text-fg hover:bg-surface"
          >
            {t('common:nav.signIn')}
          </Link>
        </div>
      </nav>

      <section
        aria-labelledby="hero-headline"
        className="mx-auto w-full max-w-6xl px-4 py-10 md:px-6 md:py-20"
      >
        <div className="grid items-center gap-10 md:grid-cols-2 md:gap-12">
          <div>
            <h1
              id="hero-headline"
              className="text-4xl font-bold leading-tight text-fg md:text-5xl"
            >
              {t('landing:hero.title')}
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-muted-fg md:text-xl">
              {t('landing:hero.subtitleLine1')}
              <br />
              {t('landing:hero.subtitleLine2')}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button
                variant="primary"
                size="lg"
                onClick={handleSignup}
                aria-label={t('landing:hero.ctaPrimaryAria')}
              >
                {t('landing:hero.ctaPrimary')}
              </Button>
              <Button variant="ghost" size="lg" asChild>
                <a href="#sample-screens" onClick={handleDemo}>
                  {t('landing:hero.ctaSecondary')}
                </a>
              </Button>
            </div>

            {SOCIAL_PROOF_COUNT >= 2000 && (
              <p className="mt-6 text-sm text-muted-fg">
                {t('landing:hero.socialProof')}
              </p>
            )}
          </div>

          <div aria-hidden="true" className="hidden md:block">
            <HeroMockup />
          </div>
        </div>
      </section>
    </>
  )
}

function HeroMockup() {
  return (
    <div className="relative mx-auto aspect-[4/5] w-full max-w-sm rounded-3xl border border-border bg-surface-raised p-6 shadow-lg">
      <div className="flex items-center justify-between">
        <div className="h-3 w-20 rounded-full bg-primary/20" />
        <div className="h-3 w-8 rounded-full bg-accent/30" />
      </div>
      <div className="mt-6 space-y-3">
        <div className="h-24 rounded-2xl bg-primary/10" />
        <div className="h-4 w-3/4 rounded-full bg-muted-fg/20" />
        <div className="h-4 w-1/2 rounded-full bg-muted-fg/20" />
      </div>
      <div className="mt-6 grid grid-cols-3 gap-2">
        <div className="h-16 rounded-xl bg-surface" />
        <div className="h-16 rounded-xl bg-surface" />
        <div className="h-16 rounded-xl bg-surface" />
      </div>
      <div className="mt-6 h-10 rounded-xl bg-primary" />
    </div>
  )
}
