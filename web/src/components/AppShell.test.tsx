import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AppShell from './AppShell'

const useAuthMock = vi.fn()
const useProfileMock = vi.fn()

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
  useProfile: () => useProfileMock(),
}))

vi.mock('../lib/useProfileLocaleSync', () => ({
  useProfileLocaleSync: () => undefined,
}))

vi.mock('./LanguageSwitcher', () => ({
  default: () => null,
}))

vi.mock('./UpgradeBanner', () => ({
  default: () => null,
}))

vi.mock('./QuotaExceededModal', () => ({
  default: () => null,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'nav.tabs.home': 'Home',
        'nav.tabs.learn': 'Learn',
        'nav.tabs.listening': 'Listening',
        'nav.tabs.reading': 'Reading',
        'nav.tabs.writing': 'Writing',
        'nav.tabs.speaking': 'Speaking',
        'nav.tabs.practice': 'Practice',
        'nav.tabs.progress': 'Progress',
        'nav.tabs.profile': 'Me',
        'nav.tabs.admin': 'Admin',
        'nav.subnav.vocab': 'Vocabulary',
        'nav.subnav.daily': 'Daily',
        'nav.subnav.review': 'Review',
        'nav.subnav.writing': 'Writing',
        'nav.subnav.listening': 'Listening',
        'nav.subnav.reading': 'Reading',
        'nav.subnav.speaking': 'Speaking',
        'nav.subnav.ariaLabel': 'Section navigation',
        'nav.comingSoon': 'Coming soon',
        'nav.speakingDisabledAriaLabel': 'Speaking — coming soon, not available',
        'nav.mainNav': 'Main navigation',
        'nav.sidebar.collapse': 'Collapse sidebar',
        'nav.sidebar.expand': 'Expand sidebar',
        'nav.signOut': 'Sign out',
        'nav.skipToContent': 'Skip to main content',
        'brand.name': 'IELTS Coach',
        'plan.badge.free': 'Free',
        'plan.badge.upgrade': 'Upgrade',
      }
      return map[key] ?? key
    },
  }),
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="*" element={<div>page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  useAuthMock.mockReturnValue({
    user: { uid: 'u1', email: 'demo@ielts.test' },
    logout: vi.fn(),
  })
  useProfileMock.mockReturnValue({ id: 'u1', name: 'Demo', plan: 'free', role: 'user' })
})

describe('<AppShell> sidebar IA — US-M15.0', () => {
  it('renders 8 top-level entries on the desktop sidebar', () => {
    renderAt('/')
    const navs = screen.getAllByRole('navigation', { name: 'Main navigation' })
    // First nav is desktop side rail, second is mobile bottom bar.
    const desktop = navs[0]
    const items = within(desktop).getAllByRole('listitem')
    expect(items).toHaveLength(8)
    // The 4 IELTS skills are present as top-level entries.
    expect(within(desktop).getByText('Listening')).toBeInTheDocument()
    expect(within(desktop).getByText('Reading')).toBeInTheDocument()
    expect(within(desktop).getByText('Writing')).toBeInTheDocument()
    expect(within(desktop).getByText('Speaking')).toBeInTheDocument()
  })

  it('renders Speaking as disabled with coming-soon badge and aria-disabled', () => {
    renderAt('/')
    const speaking = screen.getByRole('link', {
      name: 'Speaking — coming soon, not available',
    })
    expect(speaking).toHaveAttribute('aria-disabled', 'true')
    expect(speaking).toHaveAttribute('tabIndex', '-1')
    expect(within(speaking).getByText('Coming soon')).toBeInTheDocument()
  })

  it('renders mobile bottom bar with 5 entries and no Speaking', () => {
    renderAt('/')
    const navs = screen.getAllByRole('navigation', { name: 'Main navigation' })
    const mobile = navs[1]
    const items = within(mobile).getAllByRole('listitem')
    expect(items).toHaveLength(5)
    expect(within(mobile).queryByText('Speaking')).toBeNull()
  })

  it('marks the matching skill tab as current on /practice/listening', () => {
    renderAt('/practice/listening')
    const desktop = screen.getAllByRole('navigation', { name: 'Main navigation' })[0]
    const listeningLink = within(desktop).getByRole('link', { name: /Listening/ })
    expect(listeningLink).toHaveAttribute('aria-current', 'page')
  })

  it('links Learn to the vocabulary hub without showing learn subtabs', () => {
    renderAt('/learn/vocab')
    const desktop = screen.getAllByRole('navigation', { name: 'Main navigation' })[0]
    expect(within(desktop).getByRole('link', { name: /Learn/ }))
      .toHaveAttribute('href', '/learn/vocab')
    expect(screen.queryByRole('navigation', { name: 'Section navigation' }))
      .not.toBeInTheDocument()
  })
})
