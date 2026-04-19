import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useProfileLocaleSync } from '../lib/useProfileLocaleSync'
import Icon, { IconName } from './Icon'
import LanguageSwitcher from './LanguageSwitcher'
import UpgradeBanner from './UpgradeBanner'

interface Tab {
  to: string
  label: string
  icon: IconName
  /** Additional routes that should mark this tab as active */
  matches?: string[]
}

const TABS: Tab[] = [
  { to: '/', label: 'Home', icon: 'LayoutDashboard' },
  { to: '/vocab', label: 'Học', icon: 'BookOpen', matches: ['/review'] },
  { to: '/write', label: 'Luyện', icon: 'PenLine', matches: ['/listening'] },
  { to: '/progress', label: 'Tiến độ', icon: 'TrendingUp' },
  { to: '/settings', label: 'Tôi', icon: 'User' },
]

function isTabActive(tab: Tab, pathname: string): boolean {
  if (tab.to === '/') return pathname === '/'
  if (pathname.startsWith(tab.to)) return true
  return (tab.matches ?? []).some((m) => pathname.startsWith(m))
}

export default function AppShell() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  useProfileLocaleSync(!!user)

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:bg-surface-raised focus:text-fg focus:rounded-md focus:shadow-md"
      >
        Bỏ qua, đến nội dung chính
      </a>

      <div className="md:flex">
        {/* Desktop side rail (≥md) */}
        <nav
          aria-label="Điều hướng chính"
          className="hidden md:flex md:flex-col md:w-20 lg:w-60 md:border-r md:border-border md:py-4 md:px-2 md:sticky md:top-0 md:h-dvh md:shrink-0"
        >
          <div className="hidden lg:block px-3 py-2 mb-2">
            <p className="text-lg font-bold text-primary">IELTS Coach</p>
          </div>
          <ul className="flex-1 space-y-1">
            {TABS.map((t) => {
              const active = isTabActive(t, pathname)
              return (
                <li key={t.to}>
                  <NavLink
                    to={t.to}
                    aria-current={active ? 'page' : undefined}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-fast ${
                      active
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-fg hover:bg-surface hover:text-fg'
                    }`}
                  >
                    <Icon name={t.icon} size="lg" variant={active ? 'primary' : 'muted'} />
                    <span className="hidden lg:inline font-medium">{t.label}</span>
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
            <span>Đăng xuất</span>
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
        aria-label="Điều hướng chính"
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface-raised border-t border-border"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <ul className="flex">
          {TABS.map((t) => {
            const active = isTabActive(t, pathname)
            return (
              <li key={t.to} className="flex-1">
                <NavLink
                  to={t.to}
                  aria-current={active ? 'page' : undefined}
                  className={`flex flex-col items-center justify-center gap-0.5 py-2 min-h-[56px] relative transition-colors duration-fast ${
                    active ? 'text-primary' : 'text-muted-fg'
                  }`}
                >
                  {active && <span aria-hidden className="absolute top-0 inset-x-0 h-0.5 bg-primary" />}
                  <Icon name={t.icon} size="lg" variant={active ? 'primary' : 'muted'} />
                  <span className={`text-[11px] ${active ? 'font-semibold' : 'font-medium'}`}>
                    {t.label}
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
