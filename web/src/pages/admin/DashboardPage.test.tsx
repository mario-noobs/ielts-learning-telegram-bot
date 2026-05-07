import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import DashboardPage from './DashboardPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string) => k
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

const DAU = [
  { date: '2026-04-01', dau: 5, mau: 5, signups: 1 },
  { date: '2026-04-02', dau: 7, mau: 12, signups: 2 },
]
const AI = [
  { date: '2026-04-01', feature: 'vocab', count: 3 },
  { date: '2026-04-02', feature: 'writing', count: 2 },
]
const PLANS = [
  { plan_id: 'free', count: 12 },
  { plan_id: 'personal_pro', count: 4 },
]
const COHORTS = [
  { cohort_week: '2026-03-23', signups: 10, retained_d7: 6, retained_d30: 3 },
]

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('<DashboardPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  function primeAllResponses() {
    apiFetchMock.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/admin/metrics/dau')) return Promise.resolve(DAU)
      if (url.startsWith('/api/v1/admin/metrics/ai-usage')) return Promise.resolve(AI)
      if (url.startsWith('/api/v1/admin/metrics/plans')) return Promise.resolve(PLANS)
      if (url.startsWith('/api/v1/admin/metrics/cohorts')) return Promise.resolve(COHORTS)
      return Promise.resolve(null)
    })
  }

  it('renders all four metrics widgets after the API resolves', async () => {
    primeAllResponses()
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByTestId('dau-chart')).toBeInTheDocument()
      expect(screen.getByTestId('ai-usage-chart')).toBeInTheDocument()
      expect(screen.getByTestId('plan-bars')).toBeInTheDocument()
      expect(screen.getByTestId('cohort-table')).toBeInTheDocument()
    })
    // Plan rows render plan ids with their counts.
    expect(screen.getByText('free')).toBeInTheDocument()
    expect(screen.getByText('personal_pro')).toBeInTheDocument()
  })

  it('shows empty state when a section has no rows', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/admin/metrics/plans')) return Promise.resolve([])
      if (url.startsWith('/api/v1/admin/metrics/dau')) return Promise.resolve(DAU)
      if (url.startsWith('/api/v1/admin/metrics/ai-usage')) return Promise.resolve(AI)
      if (url.startsWith('/api/v1/admin/metrics/cohorts')) return Promise.resolve(COHORTS)
      return Promise.resolve(null)
    })
    renderDashboard()
    await waitFor(() => {
      expect(screen.getAllByText('dashboard.empty').length).toBeGreaterThan(0)
    })
  })

  it('shows the error string when the dashboard API fails', async () => {
    apiFetchMock.mockRejectedValue(new Error('boom'))
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('common.error')).toBeInTheDocument()
    })
  })
})
