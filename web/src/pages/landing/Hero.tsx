import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Badge, Button } from '../../components/ui'
import LanguageSwitcher from '../../components/LanguageSwitcher'
import LogoMark from '../../components/brand/LogoMark'
import { track } from '../../lib/analytics'

const SOCIAL_PROOF_COUNT = 2000

export default function Hero() {
  const { t } = useTranslation(['landing', 'common'])
  const navigate = useNavigate()

  const handleSignup = () => {
    track('landing_cta_clicked', { cta: 'signup' })
    navigate('/login')
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
          <LogoMark size="sm" />
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
        className="relative overflow-hidden"
      >
        {/* Decorative gradient blobs behind the hero content */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10"
        >
          <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-primary/20 blur-3xl" />
          <div className="absolute -right-32 top-32 h-96 w-96 rounded-full bg-accent/15 blur-3xl" />
          <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-success/10 blur-3xl" />
        </div>

        <div className="mx-auto w-full max-w-6xl px-4 py-10 md:px-6 md:py-20">
          <div className="grid items-center gap-10 md:grid-cols-2 md:gap-12">
            <div>
              <Badge
                variant="primary"
                className="mb-4 inline-flex items-center gap-1.5"
              >
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
                {t('landing:hero.eyebrow')}
              </Badge>
              <h1
                id="hero-headline"
                className="text-4xl font-bold leading-tight text-fg md:text-6xl"
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
                <p className="mt-6 flex items-center gap-2 text-sm text-muted-fg">
                  <span className="flex -space-x-2" aria-hidden="true">
                    <span className="h-6 w-6 rounded-full border-2 border-bg bg-gradient-to-br from-primary to-primary/70" />
                    <span className="h-6 w-6 rounded-full border-2 border-bg bg-gradient-to-br from-accent to-accent/70" />
                    <span className="h-6 w-6 rounded-full border-2 border-bg bg-gradient-to-br from-success to-success/70" />
                  </span>
                  {t('landing:hero.socialProof')}
                </p>
              )}
            </div>

            <div aria-hidden="true" className="relative hidden md:block">
              <HeroMockup />
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

function HeroMockup() {
  return (
    <div className="relative mx-auto w-full max-w-md">
      {/* Main mockup — wraps the existing vocab illustration in a chrome */}
      <div className="rounded-3xl border border-border bg-surface-raised p-3 shadow-2xl shadow-primary/10">
        <img
          src="/landing/vocab.svg"
          alt=""
          className="w-full rounded-2xl"
          loading="eager"
          decoding="async"
        />
      </div>

      {/* Floating badge cards — pure decorative, lg+ only */}
      <div className="absolute -left-6 top-10 hidden rounded-2xl border border-border bg-surface-raised p-3 shadow-lg lg:block">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-success/15 text-base text-success">
            ✓
          </div>
          <div>
            <div className="text-xs font-semibold text-fg">Band 7.5</div>
            <div className="text-[10px] text-muted-fg">Writing · 30s ago</div>
          </div>
        </div>
      </div>
      <div className="absolute -right-4 bottom-10 hidden rounded-2xl border border-border bg-surface-raised p-3 shadow-lg lg:block">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 font-bold text-primary">
            5
          </div>
          <div>
            <div className="text-xs font-semibold text-fg">Words today</div>
            <div className="text-[10px] text-muted-fg">Streak · 12 days</div>
          </div>
        </div>
      </div>
    </div>
  )
}
