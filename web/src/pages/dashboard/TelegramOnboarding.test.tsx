import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import TelegramOnboarding from './TelegramOnboarding'

const useAuthMock = vi.fn()
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}))

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

beforeEach(() => {
  useAuthMock.mockReset()
  apiFetchMock.mockReset()
})

function renderWidget() {
  return render(
    <MemoryRouter>
      <TelegramOnboarding />
    </MemoryRouter>,
  )
}

describe('<TelegramOnboarding> tracker (#242)', () => {
  it('shows 0/2 progress for a fresh web-only profile and skips group fetch', async () => {
    useAuthMock.mockReturnValue({
      profile: { id: 'web_x', role: 'user', plan: 'free', dismissed_onboarding: false },
      refreshProfile: vi.fn(),
    })
    renderWidget()
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    })
    // Step 1's CTA is active; Step 2's CTA is suppressed because step 1
    // isn't done yet (the row stays dimmed until the user links).
    expect(screen.getByText(/telegramOnboarding\.step1\.cta/))
      .toBeInTheDocument()
    expect(screen.queryByText(/telegramOnboarding\.step2\.cta/))
      .not.toBeInTheDocument()
    // Web-placeholder accounts shouldn't issue the groups list call —
    // it would 404 / leak a useless network request.
    expect(apiFetchMock).not.toHaveBeenCalled()
  })

  it('hides itself once both steps are complete', async () => {
    useAuthMock.mockReturnValue({
      profile: { id: '4242', role: 'user', plan: 'free', dismissed_onboarding: false },
      refreshProfile: vi.fn(),
    })
    apiFetchMock.mockResolvedValueOnce([{ id: 'g1' }])
    renderWidget()
    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/me/groups'))
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('renders nothing while the profile is still loading', () => {
    useAuthMock.mockReturnValue({ profile: null, refreshProfile: vi.fn() })
    renderWidget()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
})
