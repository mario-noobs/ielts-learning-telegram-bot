import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth, useProfile } from '../contexts/AuthContext'
import { useProfileLocaleSync } from '../lib/useProfileLocaleSync'
import Icon, { IconName } from './Icon'
import LanguageSwitcher from './LanguageSwitcher'
import LogoMark from './brand/LogoMark'
import PlanBadge from './PlanBadge'
import QuotaExceededModal from './QuotaExceededModal'
import UpgradeBanner from './UpgradeBanner'

const SIDEBAR_COLLAPSED_KEY = 'ui.sidebar.collapsed'

interface Tab {
  to: string
  labelKey: string
  icon: IconName
  /** Additional routes that should mark this tab as active */
  matches?: string[]
}

const TABS: Tab[] = [
  { to: '/', labelKey: 'nav.tabs.home', icon: 'LayoutDashboard' },
  // US-#211: route restructure → /learn/* and /practice/*. Old /vocab,
  // /write, /listening, /reading paths still redirect for bookmarks.
  { to: '/learn/daily', labelKey: 'nav.tabs.learn', icon: 'BookOpen', matches: ['/learn/', '/vocab', '/review', '/daily'] },
  { to: '/practice/writing', labelKey: 'nav.tabs.practice', icon: 'PenLine', matches: ['/practice/', '/write', '/listening', '/reading'] },
  { to: '/progress', labelKey: 'nav.tabs.progress', icon: 'TrendingUp' },
  { to: '/settings', labelKey: 'nav.tabs.profile', icon: 'User' },
]

interface SubNavItem {
  to: string
  labelKey: string
  matches?: string[]
}

const LEARN_SUBNAV: SubNavItem[] = [
  { to: '/learn/daily', labelKey: 'nav.subnav.daily', matches: ['/learn/daily'] },
  { to: '/learn/vocab', labelKey: 'nav.subnav.vocab', matches: ['/learn/vocab'] },
  { to: '/learn/review', labelKey: 'nav.subnav.review', matches: ['/learn/review'] },
]

const PRACTICE_SUBNAV: SubNavItem[] = [
  { to: '/practice/writing', labelKey: 'nav.subnav.writing', matches: ['/practice/writing'] },
  { to: '/practice/listening', labelKey: 'nav.subnav.listening', matches: ['/practice/listening'] },
  { to: '/practice/reading', labelKey: 'nav.subnav.reading', matches: ['/practice/reading'] },
]

function activeSubnav(pathname: string): SubNavItem[] | null {
  if (pathname.startsWith('/learn/')) return LEARN_SUBNAV
  if (pathname.startsWith('/practice/')) return PRACTICE_SUBNAV
  return null
}

function isSubnavActive(item: SubNavItem, pathname: string): boolean {
  return (item.matches ?? [item.to]).some((m) => pathname.startsWith(m))
}

const ADMIN_ROLES: readonly string[] = [
  'team_admin', 'org_admin', 'platform_admin',
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

  // Sidebar collapse — only takes effect at lg+ where the rail is wide
  // (md is already icon-only). Persisted across reloads.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'
  })
  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  const tabs = TABS
  const showAdminEntry =
    profile?.role !== undefined && ADMIN_ROLES.includes(profile.role)
  const planId = profile?.plan ?? 'free'

  // Width + label visibility — when collapsed, force icon-only on lg too.
  const railWidthCls = collapsed ? 'md:w-20' : 'md:w-20 lg:w-60'
  const showLabels = !collapsed

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
          className={`hidden md:flex md:flex-col ${railWidthCls} md:border-r md:border-border md:py-4 md:px-2 md:sticky md:top-0 md:h-dvh md:shrink-0`}
        >
          {showLabels ? (
            <div className="hidden lg:flex items-center gap-2 px-3 py-2 mb-2">
              <LogoMark size="sm" />
              <p className="text-lg font-bold text-primary">{t('brand.name')}</p>
            </div>
          ) : null}
          <div className={`flex items-center justify-center px-2 py-2 mb-2 ${showLabels ? 'lg:hidden' : ''}`}>
            <LogoMark size="sm" />
          </div>
          <ul className="flex-1 space-y-1">
            {tabs.map((tab) => {
              const active = isTabActive(tab, pathname)
              return (
                <li key={tab.to}>
                  <NavLink
                    to={tab.to}
                    aria-current={active ? 'page' : undefined}
                    title={collapsed ? t(tab.labelKey) : undefined}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-fast ${
                      active
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-fg hover:bg-surface hover:text-fg'
                    }`}
                  >
                    <Icon name={tab.icon} size="lg" variant={active ? 'primary' : 'muted'} />
                    {showLabels && (
                      <span className="hidden lg:inline font-medium">{t(tab.labelKey)}</span>
                    )}
                  </NavLink>
                </li>
              )
            })}
          </ul>
          {/* Account-level controls — Plan badge → Admin → Sign out → Collapse.
              Plan badge is always visible (compact letter chip when collapsed,
              full pill + Upgrade CTA for free users when expanded). */}
          <div className="border-t border-border pt-2 mt-2 space-y-1">
            {/* Full pill + Upgrade CTA — only at lg when expanded. */}
            {!collapsed && (
              <div className="hidden lg:flex px-3 py-2">
                <PlanBadge plan={planId} />
              </div>
            )}
            {/* Compact letter chip — at md always, at lg when collapsed. */}
            <div
              className={`flex justify-center px-2 py-2 ${
                collapsed ? '' : 'lg:hidden'
              }`}
            >
              <PlanBadge plan={planId} compact />
            </div>
            {showAdminEntry && (
              <NavLink
                to="/admin"
                title={collapsed ? t('nav.tabs.admin') : undefined}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-muted-fg hover:bg-surface hover:text-primary transition-colors duration-fast"
              >
                <Icon name="ShieldCheck" size="lg" variant="muted" />
                {showLabels && (
                  <span className="hidden lg:inline font-medium">
                    {t('nav.tabs.admin')}
                  </span>
                )}
              </NavLink>
            )}
            <button
              onClick={logout}
              title={collapsed ? t('nav.signOut') : undefined}
              className={`w-full items-center gap-3 px-3 py-2.5 rounded-lg text-muted-fg hover:bg-surface hover:text-danger transition-colors duration-fast ${
                collapsed ? 'flex justify-center' : 'hidden lg:flex'
              }`}
            >
              <Icon name="LogOut" size="lg" variant="muted" />
              {showLabels && <span className="hidden lg:inline">{t('nav.signOut')}</span>}
            </button>
            {/* Collapse toggle — only shown ≥lg where the wide rail exists. */}
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              aria-label={collapsed ? t('nav.sidebar.expand') : t('nav.sidebar.collapse')}
              aria-pressed={collapsed}
              className="hidden lg:flex w-full items-center justify-center gap-2 px-3 py-2 rounded-lg text-muted-fg hover:bg-surface hover:text-fg transition-colors duration-fast"
            >
              <Icon name={collapsed ? 'ChevronRight' : 'ChevronLeft'} size="md" variant="muted" />
            </button>
          </div>
        </nav>

        <main id="main" className="flex-1 min-w-0 pb-20 md:pb-0">
          <div className="flex items-center justify-end px-4 pt-3 md:px-6">
            <LanguageSwitcher persistToServer />
          </div>
          <UpgradeBanner />
          {(() => {
            const subnav = activeSubnav(pathname)
            if (!subnav) return null
            return (
              <nav
                aria-label={t('nav.subnav.ariaLabel')}
                className="border-b border-border bg-surface-raised/50 px-4 md:px-6"
              >
                <ul className="flex gap-1 overflow-x-auto">
                  {subnav.map((item) => {
                    const active = isSubnavActive(item, pathname)
                    return (
                      <li key={item.to} className="shrink-0">
                        <NavLink
                          to={item.to}
                          aria-current={active ? 'page' : undefined}
                          className={`block px-3 py-2.5 text-sm font-medium border-b-2 transition-colors duration-fast ${
                            active
                              ? 'text-primary border-primary'
                              : 'text-muted-fg border-transparent hover:text-fg'
                          }`}
                        >
                          {t(item.labelKey)}
                        </NavLink>
                      </li>
                    )
                  })}
                </ul>
              </nav>
            )
          })()}
          <Outlet />
          <QuotaExceededModal />
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
