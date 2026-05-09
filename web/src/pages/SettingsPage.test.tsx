import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import SettingsPage from './SettingsPage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string, vars?: Record<string, unknown>) => {
  if (!vars) return k
  return `${k}|${JSON.stringify(vars)}`
}
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

vi.mock('../lib/theme', () => ({
  useTheme: () => ({ pref: 'system', setPref: vi.fn() }),
}))

const PROFILE = {
  id: 'u1',
  name: 'Mario Bùi',
  email: 'mario@example.com',
  target_band: 7.0,
  topics: ['environment', 'technology'],
  streak: 5,
  exam_date: null,
  weekly_goal_minutes: 150,
  daily_time: '07:00',
  timezone: 'Asia/Ho_Chi_Minh',
  plan: 'free',
  preferred_locale: 'vi',
}

function renderPage() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

describe('<SettingsPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    apiFetchMock.mockResolvedValue(PROFILE)
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', '/settings')
    }
  })

  it('renders Profile tab by default with name + email + timezone fields', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByDisplayValue('Mario Bùi')).toBeInTheDocument()
    })
    expect(screen.getByDisplayValue('mario@example.com')).toBeInTheDocument()
    // Timezone select shows the user's tz
    expect(screen.getByLabelText('profile.timezone')).toBeInTheDocument()
  })

  it('switches to Practice tab and renders topics chips + daily time', async () => {
    renderPage()
    await waitFor(() => screen.getByDisplayValue('Mario Bùi'))
    await userEvent.click(screen.getByRole('tab', { name: 'tabs.practice' }))
    expect(screen.getByText('environment')).toBeInTheDocument()
    expect(screen.getByText('technology')).toBeInTheDocument()
    expect(screen.getByLabelText('practice.dailyTime')).toBeInTheDocument()
  })

  it('shows Free plan chip + Upgrade CTA on Plan tab when plan=free', async () => {
    renderPage()
    await waitFor(() => screen.getByDisplayValue('Mario Bùi'))
    await userEvent.click(screen.getByRole('tab', { name: 'tabs.plan' }))
    expect(screen.getByText('plan.badge.free')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'plan.upgrade' })).toBeInTheDocument()
  })
})
