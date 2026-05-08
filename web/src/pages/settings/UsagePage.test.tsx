import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import UsagePage from './UsagePage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('../../contexts/AuthContext', () => ({
  // The page only consumes `useProfile()`. Default to a free user
  // without a custom override; individual tests override as needed.
  useProfile: () => ({ id: 'u1', plan: 'free', role: 'user', name: 'X' }),
}))

const t = (key: string, vars?: Record<string, unknown>) => {
  if (!vars) return key
  return `${key}|${JSON.stringify(vars)}`
}
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

const TODAY = {
  plan: 'free',
  quota_daily: 10,
  used_today: 4,
  by_feature: [
    { feature: 'quiz', count: 2 },
    { feature: 'writing', count: 2 },
  ],
  reset_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
}

function primeApi(history: unknown[]) {
  apiFetchMock.mockImplementation((url: string) => {
    if (url === '/api/v1/me/ai-usage') return Promise.resolve(TODAY)
    if (url.startsWith('/api/v1/me/ai-usage/history'))
      return Promise.resolve(history)
    return Promise.resolve(null)
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <UsagePage />
    </MemoryRouter>,
  )
}

describe('<UsagePage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders the today summary after the API resolves', async () => {
    primeApi([])
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('usage-today-card')).toBeInTheDocument()
    })
    // Per-feature breakdown is always expanded on this page.
    const breakdown = screen.getByTestId('usage-today-breakdown')
    expect(within(breakdown).getByText('quiz')).toBeInTheDocument()
    expect(within(breakdown).getByText('writing')).toBeInTheDocument()
  })

  it('renders the chart when history has rows', async () => {
    const history = [
      { date: '2026-04-25', feature: 'quiz', count: 3 },
      { date: '2026-04-26', feature: 'writing', count: 2 },
    ]
    primeApi(history)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('ai-usage-chart')).toBeInTheDocument()
    })
  })

  it('shows ↑ delta when last 7 days exceed the prior 7', async () => {
    // 14 daily rows: day -13..-7 each with count=1 (prev7 total=7),
    // day -6..0 each with count=2 (last7 total=14) → +100% up.
    const today = new Date()
    const history: { date: string; feature: string; count: number }[] = []
    for (let i = 0; i < 14; i++) {
      const d = new Date(today.getTime() - i * 86400000)
      const iso = d.toISOString().slice(0, 10)
      history.push({ date: iso, feature: 'quiz', count: i < 7 ? 2 : 1 })
    }
    primeApi(history)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('usage-delta')).toBeInTheDocument()
    })
    const delta = screen.getByTestId('usage-delta')
    expect(delta.textContent || '').toContain('vsLast7Up')
    expect(delta.textContent || '').toContain('100')
  })

  it('paginates the history table at 10 rows per page', async () => {
    // 12 distinct days → 2 pages of 10.
    const today = new Date()
    const history: { date: string; feature: string; count: number }[] = []
    for (let i = 0; i < 12; i++) {
      const d = new Date(today.getTime() - i * 86400000)
      const iso = d.toISOString().slice(0, 10)
      history.push({ date: iso, feature: 'quiz', count: 1 })
    }
    primeApi(history)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('usage-history-table')).toBeInTheDocument()
    })
    const initialRows = screen
      .getByTestId('usage-history-table')
      .querySelectorAll('tbody tr')
    expect(initialRows.length).toBe(10)
    // Click "next" → page 2 should show the remaining 2 rows.
    const next = screen.getByRole('button', { name: /pagination.next/ })
    await userEvent.click(next)
    const page2Rows = screen
      .getByTestId('usage-history-table')
      .querySelectorAll('tbody tr')
    expect(page2Rows.length).toBe(2)
  })
})
