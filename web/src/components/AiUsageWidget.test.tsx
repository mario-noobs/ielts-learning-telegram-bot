import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import AiUsageWidget from './AiUsageWidget'

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

function renderWidget() {
  return render(
    <MemoryRouter>
      <AiUsageWidget />
    </MemoryRouter>,
  )
}

describe('<AiUsageWidget>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders progress bar + plan chip after the API resolves', async () => {
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 7,
      by_feature: [{ feature: 'quiz', count: 4 }, { feature: 'writing', count: 3 }],
      reset_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
    })
    renderWidget()
    await waitFor(() => {
      expect(screen.getByTestId('ai-usage-widget')).toBeInTheDocument()
    })
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '70')
    expect(screen.getByText('free')).toBeInTheDocument()
  })

  it('renders the saturated state when used >= quota', async () => {
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 12,
      by_feature: [],
      reset_at: new Date(Date.now() + 60_000).toISOString(),
    })
    renderWidget()
    await waitFor(() => {
      expect(screen.getByText('aiUsage.saturated.title')).toBeInTheDocument()
    })
    // Clamped: used (12) capped to cap (10) for display.
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })

  it('renders the empty state when used = 0', async () => {
    apiFetchMock.mockResolvedValueOnce({
      plan: 'free',
      quota_daily: 10,
      used_today: 0,
      by_feature: [],
      reset_at: new Date(Date.now() + 8 * 3600 * 1000).toISOString(),
    })
    renderWidget()
    await waitFor(() => {
      expect(screen.getByText('aiUsage.empty')).toBeInTheDocument()
    })
  })
})
