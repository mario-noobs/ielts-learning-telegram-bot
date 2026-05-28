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
  /** Renders as a non-navigable, dimmed entry with a "coming soon" badge. */
  disabled?: boolean
  /** Aria label used when disabled, so screen readers announce the unavailable state. */
  disabledAriaKey?: string
}

// US-M15.0: sidebar splits "Practice" into 4 IELTS-skill top-level entries.
// Speaking has no surface yet — disabled with "coming soon" affordance.
// US-#211 redirects keep old /vocab, /write, /listening, /reading bookmarks alive.
const TABS: Tab[] = [
  { to: '/', labelKey: 'nav.tabs.home', icon: 'LayoutDashboard' },
  { to: '/learn/vocab', labelKey: 'nav.tabs.learn', icon: 'BookOpen', matches: ['/learn/vocab', '/learn/review', '/learn/daily', '/vocab', '/review', '/daily'] },
  { to: '/learn/pools', labelKey: 'nav.tabs.pools', icon: 'Globe' },
  { to: '/team', labelKey: 'nav.tabs.team', icon: 'Users' },
  { to: '/practice/listening', labelKey: 'nav.tabs.listening', icon: 'Headphones', matches: ['/practice/listening', '/listening'] },
  { to: '/practice/reading', labelKey: 'nav.tabs.reading', icon: 'FileText', matches: ['/practice/reading', '/reading'] },
  { to: '/practice/writing', labelKey: 'nav.tabs.writing', icon: 'PenLine', matches: ['/practice/writing', '/write'] },
  { to: '/practice/speaking', labelKey: 'nav.tabs.speaking', icon: 'Mic', disabled: true, disabledAriaKey: 'nav.speakingDisabledAriaLabel' },
  { to: '/progress', labelKey: 'nav.tabs.progress', icon: 'TrendingUp' },
  { to: '/settings', labelKey: 'nav.tabs.profile', icon: 'User' },
]

// Mobile bottom bar can't fit every desktop entry. Keep IELTS skills grouped
// under Practice, but expose Pools because it is no longer part of Vocabulary.
const MOBILE_TABS: Tab[] = [
  { to: '/', labelKey: 'nav.tabs.home', icon: 'LayoutDashboard' },
  { to: '/learn/vocab', labelKey: 'nav.tabs.learn', icon: 'BookOpen', matches: ['/learn/vocab', '/learn/review', '/learn/daily', '/vocab', '/review', '/daily'] },
  { to: '/learn/pools', labelKey: 'nav.tabs.pools', icon: 'Globe' },
  { to: '/team', labelKey: 'nav.tabs.team', icon: 'Users' },
  { to: '/practice/writing', labelKey: 'nav.tabs.practice', icon: 'PenLine', matches: ['/practice/', '/write', '/listening', '/reading'] },
  { to: '/progress', labelKey: 'nav.tabs.progress', icon: 'TrendingUp' },
  { to: '/settings', labelKey: 'nav.tabs.profile', icon: 'User' },
]

interface SubNavItem {
  to: string
  labelKey: string
  matches?: string[]
  disabled?: boolean
}

const PRACTICE_SUBNAV: SubNavItem[] = [
  { to: '/practice/writing', labelKey: 'nav.subnav.writing', matches: ['/practice/writing'] },
  { to: '/practice/listening', labelKey: 'nav.subnav.listening', matches: ['/practice/listening'] },
  { to: '/practice/reading', labelKey: 'nav.subnav.reading', matches: ['/practice/reading'] },
  { to: '/practice/speaking', labelKey: 'nav.subnav.speaking', disabled: true },
]

function activeSubnav(pathname: string): SubNavItem[] | null {
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
  const mobileTabs = MOBILE_TABS
  const showAdminEntry =
    profile?.role !== undefined && ADMIN_ROLES.includes(profile.role)
  const planId = profile?.plan ?? 'free'

  // Width + label visibility — when collapsed, force icon-only on lg too.
  const railWidthCls = collapsed ? 'md:w-20' : 'md:w-20 lg:w-60'
  const showLabels = !collapsed

  // Account-card data (avatar initial + display name).
  const displayName =
    profile?.name?.trim() ||
    user?.displayName?.trim() ||
    user?.email?.split('@')[0] ||
    ''
  const initial =
    (displayName || user?.email || '?').trim()[0]?.toUpperCase() ?? '?'

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
          {/* Header — brand mark + wordmark (lg-expanded) + collapse toggle.
              Toggle moves with the brand instead of floating at the bottom,
              following the pattern used by Linear/Vercel sidebars. */}
          {!collapsed ? (
            <>
              <div className="hidden lg:flex items-center gap-2 px-3 py-2 mb-3">
                <LogoMark size="sm" />
                <p className="text-base font-semibold text-fg">{t('brand.name')}</p>
                <button
                  type="button"
                  onClick={() => setCollapsed(true)}
                  aria-label={t('nav.sidebar.collapse')}
                  className="ml-auto p-1 rounded-md text-muted-fg hover:bg-surface hover:text-fg transition-colors"
                >
                  <Icon name="ChevronLeft" size="sm" variant="muted" />
                </button>
              </div>
              <div className="flex lg:hidden items-center justify-center px-2 py-2 mb-2">
                <LogoMark size="sm" />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2 px-2 py-2 mb-2">
              <LogoMark size="sm" />
              <button
                type="button"
                onClick={() => setCollapsed(false)}
                aria-label={t('nav.sidebar.expand')}
                className="hidden lg:inline-flex p-1 rounded-md text-muted-fg hover:bg-surface hover:text-fg transition-colors"
              >
                <Icon name="ChevronRight" size="sm" variant="muted" />
              </button>
            </div>
          )}

          <ul className="flex-1 min-h-0 overflow-y-auto space-y-0.5">
            {tabs.map((tab) => {
              if (tab.disabled) {
                const ariaLabel = tab.disabledAriaKey ? t(tab.disabledAriaKey) : t(tab.labelKey)
                return (
                  <li key={tab.to}>
                    <span
                      role="link"
                      aria-disabled="true"
                      aria-label={ariaLabel}
                      tabIndex={-1}
                      title={collapsed ? ariaLabel : undefined}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-muted-fg opacity-50 cursor-not-allowed"
                    >
                      <Icon name={tab.icon} size="lg" variant="muted" />
                      {showLabels && (
                        <span className="hidden lg:inline-flex lg:items-center lg:gap-2 font-medium">
                          {t(tab.labelKey)}
                          <span className="rounded-full bg-muted-fg/10 px-2 py-0.5 text-[10px] uppercase tracking-wide">
                            {t('nav.comingSoon')}
                          </span>
                        </span>
                      )}
                    </span>
                  </li>
                )
              }
              const active = isTabActive(tab, pathname)
              return (
                <li key={tab.to}>
                  <NavLink
                    to={tab.to}
                    aria-current={active ? 'page' : undefined}
                    title={collapsed ? t(tab.labelKey) : undefined}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors duration-fast ${
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

          {/* Account block — single cohesive card at lg-expanded; stacked
              icon column at md and lg-collapsed. Replaces the previous
              loose stack of badge + admin + signout + toggle. */}
          <div className="mt-3 pt-3 border-t border-border">
            {!collapsed && (
              <div className="hidden lg:block space-y-1">
                <div className="rounded-xl border border-border p-3 space-y-2.5">
                  <div className="flex items-center gap-2.5">
                    <span
                      aria-hidden="true"
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold"
                    >
                      {initial}
                    </span>
                    <p
                      className="flex-1 truncate text-sm font-medium text-fg"
                      title={displayName}
                    >
                      {displayName}
                    </p>
                    <button
                      type="button"
                      onClick={logout}
                      aria-label={t('nav.signOut')}
                      className="rounded-md p-1.5 text-muted-fg hover:bg-surface-raised hover:text-danger transition-colors"
                    >
                      <Icon name="LogOut" size="md" variant="muted" />
                    </button>
                  </div>
                  <PlanBadge plan={planId} />
                </div>
                {showAdminEntry && (
                  <NavLink
                    to="/admin"
                    className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted-fg hover:bg-surface hover:text-primary transition-colors"
                  >
                    <Icon name="ShieldCheck" size="sm" variant="muted" />
                    <span>{t('nav.tabs.admin')}</span>
                  </NavLink>
                )}
              </div>
            )}

            <div
              className={`flex flex-col items-center gap-2 ${
                collapsed ? '' : 'lg:hidden'
              }`}
            >
              <span
                aria-hidden="true"
                title={displayName}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold"
              >
                {initial}
              </span>
              <PlanBadge plan={planId} compact />
              {showAdminEntry && (
                <NavLink
                  to="/admin"
                  title={t('nav.tabs.admin')}
                  className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-fg hover:bg-surface hover:text-primary transition-colors"
                >
                  <Icon name="ShieldCheck" size="md" variant="muted" />
                </NavLink>
              )}
              <button
                type="button"
                onClick={logout}
                aria-label={t('nav.signOut')}
                title={t('nav.signOut')}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-fg hover:bg-surface hover:text-danger transition-colors"
              >
                <Icon name="LogOut" size="md" variant="muted" />
              </button>
            </div>
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
            // Hide practice subnav on lg+ — desktop sidebar already exposes
            // the 4 skills as top-level entries (M15.0).
            const hideOnDesktop = subnav === PRACTICE_SUBNAV
            return (
              <nav
                aria-label={t('nav.subnav.ariaLabel')}
                className={`border-b border-border bg-surface-raised/50 px-4 md:px-6 ${
                  hideOnDesktop ? 'lg:hidden' : ''
                }`}
              >
                <ul className="flex gap-1 overflow-x-auto">
                  {subnav.map((item) => {
                    if (item.disabled) {
                      return (
                        <li key={item.to} className="shrink-0">
                          <span
                            role="link"
                            aria-disabled="true"
                            tabIndex={-1}
                            className="inline-flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 border-transparent text-muted-fg opacity-50 cursor-not-allowed"
                          >
                            {t(item.labelKey)}
                            <span className="rounded-full bg-muted-fg/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
                              {t('nav.comingSoon')}
                            </span>
                          </span>
                        </li>
                      )
                    }
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

      {/* Mobile bottom tab bar (<md) — separate 5-tab subset since the
          full 8-entry desktop sidebar can't fit in a bottom bar. Cross-skill
          navigation on mobile lives in PRACTICE_SUBNAV. */}
      <nav
        aria-label={t('nav.mainNav')}
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface-raised border-t border-border"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <ul className="flex">
          {mobileTabs.map((tab) => {
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
