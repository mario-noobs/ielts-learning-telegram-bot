import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import PlansPage from './PlansPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}))

const PLANS_PAYLOAD = [
  {
    id: 'free', name: 'Free',
    daily_ai_quota: 10, monthly_ai_quota: 200,
    max_team_seats: null, features: [], created_at: null,
  },
]

describe('<PlansPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders rows from the API', async () => {
    apiFetchMock.mockResolvedValueOnce(PLANS_PAYLOAD)
    render(<PlansPage />)
    await waitFor(() => {
      expect(screen.getByText('free')).toBeInTheDocument()
      expect(screen.getByText('Free')).toBeInTheDocument()
    })
  })

  it('opens the create form on createCta click', async () => {
    apiFetchMock.mockResolvedValueOnce([])
    render(<PlansPage />)
    await waitFor(() => screen.getByText('plans.empty'))

    await userEvent.click(screen.getByRole('button', { name: 'plans.createCta' }))
    expect(screen.getByText('plans.form.id')).toBeInTheDocument()
  })

  it('PATCHes plan updates and refreshes the list', async () => {
    apiFetchMock
      .mockResolvedValueOnce(PLANS_PAYLOAD)            // initial GET
      .mockResolvedValueOnce({ ok: true, audit_log_id: 1 })  // PATCH
      .mockResolvedValueOnce([                              // refresh GET
        { ...PLANS_PAYLOAD[0], daily_ai_quota: 99 },
      ])
    render(<PlansPage />)
    await waitFor(() => screen.getByText('Free'))

    await userEvent.click(screen.getByRole('button', { name: 'actions.edit' }))
    const dailyInput = screen.getAllByRole('spinbutton')[0] as HTMLInputElement
    await userEvent.clear(dailyInput)
    await userEvent.type(dailyInput, '99')
    await userEvent.click(screen.getByRole('button', { name: 'plans.form.save' }))

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/plans/free',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })
})
