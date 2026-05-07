import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import TeamsPage from './TeamsPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string) => k
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

const TEAMS_PAYLOAD = [
  {
    id: 't1', name: 'Alpha', owner_uid: 'u-a',
    plan_id: 'team_member', plan_expires_at: null,
    seat_limit: 5, created_by: 'u-a', created_at: null,
    member_count: 2,
  },
]

describe('<TeamsPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders rows returned from the API', async () => {
    apiFetchMock.mockResolvedValueOnce(TEAMS_PAYLOAD)
    render(
      <MemoryRouter>
        <TeamsPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText('Alpha')).toBeInTheDocument()
    })
    // 'team_member' also appears in the create-form <select>, so just
    // assert that the row's seat count rendered.
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('renders the empty state when the list is empty', async () => {
    apiFetchMock.mockResolvedValueOnce([])
    render(
      <MemoryRouter>
        <TeamsPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText('teams.empty')).toBeInTheDocument()
    })
  })

  it('POSTs to /admin/teams when the create form is submitted', async () => {
    apiFetchMock
      .mockResolvedValueOnce([])                            // initial list
      .mockResolvedValueOnce({ ok: true, extra: { id: 't1' } }) // create
      .mockResolvedValueOnce(TEAMS_PAYLOAD)                 // refresh list
    render(
      <MemoryRouter>
        <TeamsPage />
      </MemoryRouter>,
    )
    await waitFor(() => screen.getByText('teams.empty'))

    await userEvent.type(
      screen.getByPlaceholderText('teams.form.name'),
      'Alpha',
    )
    await userEvent.type(
      screen.getByPlaceholderText('teams.form.ownerUid'),
      'u-a',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'teams.form.create' }),
    )

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/teams',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
})
