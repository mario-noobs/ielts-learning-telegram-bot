import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth, useProfile } from '../contexts/AuthContext'
import { useProfileLocaleSync } from '../lib/useProfileLocaleSync'
import Icon, { IconName } from './Icon'
import LanguageSwitcher from './LanguageSwitcher'
import UpgradeBanner from './UpgradeBanner'

interface Tab {
  to: string
  labelKey: string
  icon: IconName
  /** Additional routes that should mark this tab as active */
  matches?: string[]
  /** Hide unless the user's role is one of these (default: visible to all) */
  requiresRole?: ReadonlyArray<'team_admin' | 'org_admin' | 'platform_admin'>
}

const TABS: Tab[] = [
  { to: '/', labelKey: 'nav.tabs.home', icon: 'LayoutDashboard' },
  { to: '/vocab', labelKey: 'nav.tabs.learn', icon: 'BookOpen', matches: ['/review'] },
  { to: '/write', labelKey: 'nav.tabs.practice', icon: 'PenLine', matches: ['/listening', '/reading'] },
  { to: '/progress', labelKey: 'nav.tabs.progress', icon: 'TrendingUp' },
  { to: '/settings', labelKey: 'nav.tabs.profile', icon: 'User' },
  {
    to: '/admin',
    labelKey: 'nav.tabs.admin',
    icon: 'ShieldCheck',
    requiresRole: ['team_admin', 'org_admin', 'platform_admin'],
  },
]

function isTabActive(tab: Tab, pathname: string): boolean {
  if (tab.to === '/') return pathname === '/'
  if (pathname.startsWith(tab.to)) return true
  return (tab.matches ?? []).some((m) => pathname.startsWith(m))
}

export default function AppShell() {
  const { t } = useTranslation('common')
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const profile = useProfile()
  useProfileLocaleSync(!!user)

  const tabs = TABS.filter((tab) => {
    if (!tab.requiresRole) return true
    return profile?.role !== undefined && profile.role !== 'user'
        && tab.requiresRole.includes(profile.role)
  })

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:bg-surface-raised focus:text-fg focus:rounded-md focus:shadow-md"
      >
        {t('nav.skipToContent')}
      </a>

      <div className="md:flex">
        {/* Desktop side rail (≥md) */}
        <nav
          aria-label={t('nav.mainNav')}
          className="hidden md:flex md:flex-col md:w-20 lg:w-60 md:border-r md:border-border md:py-4 md:px-2 md:sticky md:top-0 md:h-dvh md:shrink-0"
        >
          <div className="hidden lg:block px-3 py-2 mb-2">
            <p className="text-lg font-bold text-primary">{t('brand.name')}</p>
          </div>
          <ul className="flex-1 space-y-1">
            {tabs.map((tab) => {
              const active = isTabActive(tab, pathname)
              return (
                <li key={tab.to}>
                  <NavLink
                    to={tab.to}
                    aria-current={active ? 'page' : undefined}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-fast ${
                      active
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-fg hover:bg-surface hover:text-fg'
                    }`}
                  >
                    <Icon name={tab.icon} size="lg" variant={active ? 'primary' : 'muted'} />
                    <span className="hidden lg:inline font-medium">{t(tab.labelKey)}</span>
                  </NavLink>
                </li>
              )
            })}
          </ul>
          <button
            onClick={logout}
            className="hidden lg:flex items-center gap-3 px-3 py-2.5 rounded-lg text-muted-fg hover:bg-surface hover:text-danger transition-colors duration-fast"
          >
            <Icon name="LogOut" size="lg" variant="muted" />
            <span>{t('nav.signOut')}</span>
          </button>
        </nav>

        <main id="main" className="flex-1 min-w-0 pb-20 md:pb-0">
          <div className="flex items-center justify-end px-4 pt-3 md:px-6">
            <LanguageSwitcher persistToServer />
          </div>
          <UpgradeBanner />
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom tab bar (<md) */}
      <nav
        aria-label={t('nav.mainNav')}
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface-raised border-t border-border"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <ul className="flex">
          {tabs.map((tab) => {
            const active = isTabActive(tab, pathname)
            return (
              <li key={tab.to} className="flex-1">
                <NavLink
                  to={tab.to}
                  aria-current={active ? 'page' : undefined}
                  className={`flex flex-col items-center justify-center gap-0.5 py-2 min-h-[56px] relative transition-colors duration-fast ${
                    active ? 'text-primary' : 'text-muted-fg'
                  }`}
                >
                  {active && <span aria-hidden className="absolute top-0 inset-x-0 h-0.5 bg-primary" />}
                  <Icon name={tab.icon} size="lg" variant={active ? 'primary' : 'muted'} />
                  <span className={`text-[11px] ${active ? 'font-semibold' : 'font-medium'}`}>
                    {t(tab.labelKey)}
                  </span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
