import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import Icon, { IconName } from './Icon'

/** Admin section nav (US-M11.6).
 *  Lives entirely outside the consumer ``AppShell`` — no learner tabs,
 *  no upgrade banner, no language switcher header. ``Back to app`` is
 *  always reachable in the top bar. */

interface AdminSection {
  to: string
  labelKey: string
  icon: IconName
  /** Additional path prefixes that should mark this section active. */
  matches?: string[]
}

const SECTIONS: AdminSection[] = [
  { to: '/admin', labelKey: 'admin.nav.dashboard', icon: 'LayoutDashboard' },
  { to: '/admin/users', labelKey: 'admin.nav.users', icon: 'User' },
  { to: '/admin/teams', labelKey: 'admin.nav.teams', icon: 'BookOpen' },
  { to: '/admin/orgs', labelKey: 'admin.nav.orgs', icon: 'ShieldCheck' },
  { to: '/admin/plans', labelKey: 'admin.nav.plans', icon: 'TrendingUp' },
  { to: '/admin/flags', labelKey: 'admin.nav.flags', icon: 'PenLine' },
  { to: '/admin/audit', labelKey: 'admin.nav.audit', icon: 'LogOut' },
]

function isSectionActive(section: AdminSection, pathname: string): boolean {
  if (section.to === '/admin') return pathname === '/admin'
  if (pathname.startsWith(section.to)) return true
  return (section.matches ?? []).some((m) => pathname.startsWith(m))
}

export default function AdminShell() {
  const { t } = useTranslation('common')
  const { t: tAdmin } = useTranslation('admin')
  const { pathname } = useLocation()

  return (
    <div className="min-h-dvh bg-bg text-fg flex flex-col">
      <header className="sticky top-0 z-30 bg-surface-raised border-b border-border">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4 px-4 md:px-6 h-14">
          <div className="flex items-center gap-3">
            <span className="text-base font-bold text-primary">
              {t('brand.name')}
            </span>
            <span className="text-sm text-muted-fg hidden sm:inline">
              · {tAdmin('shell.label')}
            </span>
          </div>
          <Link
            to="/"
            className="text-sm text-primary hover:underline flex items-center gap-1.5"
          >
            <Icon name="LogOut" size="sm" variant="primary" />
            {tAdmin('shell.backToApp')}
          </Link>
        </div>
        <nav
          aria-label={tAdmin('shell.sectionNav')}
          className="border-t border-border bg-surface"
        >
          <ul className="max-w-7xl mx-auto flex gap-1 px-2 md:px-4 overflow-x-auto">
            {SECTIONS.map((s) => {
              const active = isSectionActive(s, pathname)
              return (
                <li key={s.to} className="shrink-0">
                  <NavLink
                    to={s.to}
                    end={s.to === '/admin'}
                    aria-current={active ? 'page' : undefined}
                    className={`flex items-center gap-2 px-3 py-2.5 text-sm transition-colors duration-fast border-b-2 ${
                      active
                        ? 'text-primary border-primary'
                        : 'text-muted-fg border-transparent hover:text-fg hover:bg-surface-raised'
                    }`}
                  >
                    <Icon
                      name={s.icon}
                      size="sm"
                      variant={active ? 'primary' : 'muted'}
                    />
                    <span>{tAdmin(s.labelKey)}</span>
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </nav>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 md:px-6 py-6 space-y-6">
        <Outlet />
      </main>
    </div>
  )
}
