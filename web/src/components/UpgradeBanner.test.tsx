import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import UpgradeBanner from './UpgradeBanner'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (key: string, vars?: Record<string, unknown>) => {
  if (!vars) return key
  return `${key}|${JSON.stringify(vars)}`
}
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

function renderBanner(initialPath = '/write') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <UpgradeBanner />
    </MemoryRouter>,
  )
}

describe('<UpgradeBanner> (US-M13.3)', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    sessionStorage.clear()
  })

  it('appears at 80% on a protected route', async () => {
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 8, // 80%
      by_feature: [],
      reset_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
    })
    renderBanner('/write')
    await waitFor(() => {
      expect(
        screen.getByText('aiUsage.banner.warn80.title'),
      ).toBeInTheDocument()
    })
  })

  it('is hidden on the Dashboard route', async () => {
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 9,
      by_feature: [],
      reset_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
    })
    renderBanner('/')
    // No async wait — banner should never render on `/`. Allow microtasks
    // to flush so the fetch promise can resolve.
    await act(async () => {
      await Promise.resolve()
    })
    expect(
      screen.queryByText('aiUsage.banner.warn80.title'),
    ).not.toBeInTheDocument()
  })

  it('persists dismissal in sessionStorage', async () => {
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 8,
      by_feature: [],
      reset_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
    })
    const user = userEvent.setup()
    const { unmount } = renderBanner('/write')
    await waitFor(() => {
      expect(
        screen.getByText('aiUsage.banner.warn80.title'),
      ).toBeInTheDocument()
    })
    // The dismiss button is the trailing icon-button, identified by its
    // aria-label which we set to the banner title key (only one exists).
    const dismissBtn = screen
      .getAllByLabelText('aiUsage.banner.warn80.title')
      .find((el) => el.tagName === 'BUTTON')!
    await user.click(dismissBtn)
    expect(sessionStorage.getItem('quota.banner.dismissed')).toBe('1')

    // Re-render in same session — banner should stay dismissed.
    unmount()
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 8,
      by_feature: [],
      reset_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
    })
    renderBanner('/write')
    await act(async () => {
      await Promise.resolve()
    })
    expect(
      screen.queryByText('aiUsage.banner.warn80.title'),
    ).not.toBeInTheDocument()
  })
})
