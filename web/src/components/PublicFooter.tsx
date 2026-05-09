import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import LanguageSwitcher from './LanguageSwitcher'
import LogoMark from './brand/LogoMark'

/** Slim footer for public pages (Login / Pricing / Privacy / Terms).
 *  Mounted only inside `PublicLayout`; do NOT mount inside the
 *  authenticated AppShell — protected pages are task surfaces and
 *  the footer steals vertical space. */

export default function PublicFooter() {
  const { t } = useTranslation('landing')
  const { t: tCommon } = useTranslation('common')
  const year = new Date().getFullYear()

  return (
    <footer
      className="border-t border-border bg-bg px-4 py-10 sm:px-6"
      aria-labelledby="public-footer-heading"
    >
      <h2 id="public-footer-heading" className="sr-only">
        {tCommon('nav.legalNav')}
      </h2>
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          <div>
            <Link to="/" className="flex items-center gap-2 text-base font-bold text-fg">
              <LogoMark size="sm" />
              {tCommon('brand.name')}
            </Link>
            <p className="mt-2 text-sm leading-relaxed text-muted-fg">
              {t('footer.tagline')}
            </p>
            <div className="mt-3">
              <LanguageSwitcher />
            </div>
          </div>

          <nav aria-label={t('footer.columns.product')}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-fg">
              {t('footer.columns.product')}
            </h3>
            <ul className="space-y-1.5 text-sm">
              <li>
                <Link to="/pricing" className="text-fg hover:text-primary">
                  {t('footer.links.pricing')}
                </Link>
              </li>
            </ul>
          </nav>

          <nav aria-label={t('footer.columns.legal')}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-fg">
              {t('footer.columns.legal')}
            </h3>
            <ul className="space-y-1.5 text-sm">
              <li>
                <Link to="/privacy" className="text-fg hover:text-primary">
                  {t('footer.links.privacy')}
                </Link>
              </li>
              <li>
                <Link to="/terms" className="text-fg hover:text-primary">
                  {t('footer.links.terms')}
                </Link>
              </li>
            </ul>
          </nav>

          <nav aria-label={t('footer.columns.contact')}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-fg">
              {t('footer.columns.contact')}
            </h3>
            <ul className="space-y-1.5 text-sm">
              <li>
                <a
                  href={`mailto:${t('footer.links.email')}`}
                  className="text-fg hover:text-primary"
                >
                  {t('footer.links.email')}
                </a>
              </li>
            </ul>
          </nav>
        </div>

        <div className="mt-8 border-t border-border pt-4 text-xs text-muted-fg">
          {t('footer.copyright', { year })}
        </div>
      </div>
    </footer>
  )
}
