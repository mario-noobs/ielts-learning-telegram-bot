import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui'
import Pricing from './landing/Pricing'
import FAQ from './landing/FAQ'
import Footer from './landing/Footer'

export default function PricingPage() {
  const { t } = useTranslation(['common', 'landing'])
  useEffect(() => {
    const previous = document.title
    document.title = `${t('landing:pricingTitle', { defaultValue: 'Pricing' })} — ${t('common:brand.name')}`
    return () => {
      document.title = previous
    }
  }, [t])

  return (
    <div className="min-h-dvh overflow-x-hidden bg-bg text-fg">
      <nav
        aria-label={t('common:nav.legalNav')}
        className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 md:px-6"
      >
        <Link to="/" className="flex items-center gap-2 text-lg font-bold text-fg">
          {t('common:brand.name')}
          <Badge variant="primary" aria-label={t('common:auth.brandBetaLabel')}>
            {t('common:brand.beta')}
          </Badge>
        </Link>
        <Link
          to="/"
          className="rounded-xl px-3 py-2 text-sm font-medium text-muted-fg hover:bg-surface hover:text-fg"
        >
          ← {t('common:actions.goToDashboard')}
        </Link>
      </nav>
      <main>
        <Pricing />
        <FAQ />
      </main>
      <Footer />
    </div>
  )
}
