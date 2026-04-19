import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import Hero from './landing/Hero'
import ValueProps from './landing/ValueProps'
import Pricing from './landing/Pricing'
import Testimonials from './landing/Testimonials'
import FAQ from './landing/FAQ'
import Footer from './landing/Footer'

export default function LandingPage() {
  const { t } = useTranslation(['landing', 'common'])
  useEffect(() => {
    const previous = document.title
    document.title = `${t('common:brand.name')} — ${t('landing:pageTitle', { defaultValue: 'Practice IELTS every day' })}`
    return () => {
      document.title = previous
    }
  }, [t])

  return (
    <div className="min-h-dvh overflow-x-hidden bg-bg text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-surface-raised focus:px-4 focus:py-2 focus:text-fg"
      >
        {t('common:nav.skipToContent')}
      </a>
      <main id="main">
        <Hero />
        <ValueProps />
        <section id="sample-screens" aria-hidden="true" />
        <Pricing />
        <Testimonials />
        <FAQ />
      </main>
      <Footer />
    </div>
  )
}
