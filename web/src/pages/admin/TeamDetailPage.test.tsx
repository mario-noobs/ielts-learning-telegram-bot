import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import TeamDetailPage from './TeamDetailPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string) => k
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

const TEAM = {
  id: 't1', name: 'Alpha', owner_uid: 'u-a',
  plan_id: 'team_member', plan_expires_at: null,
  seat_limit: 5, created_by: 'u-a', created_at: null,
  member_count: 1,
}
const MEMBERS = [{ user_uid: 'u-1', role: 'member', joined_at: null }]

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/teams/:id" element={<TeamDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<TeamDetailPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders the team header + member list from the API', async () => {
    apiFetchMock
      .mockResolvedValueOnce(TEAM)     // GET /teams/:id
      .mockResolvedValueOnce(MEMBERS)  // GET /teams/:id/members

    renderAt('/admin/teams/t1')
    await waitFor(() => {
      expect(screen.getByText('Alpha')).toBeInTheDocument()
      expect(screen.getByText('u-1')).toBeInTheDocument()
    })
  })

  it('POSTs a new member when the add-member form is submitted', async () => {
    apiFetchMock
      .mockResolvedValueOnce(TEAM)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ ok: true })          // POST member
      .mockResolvedValueOnce({ ...TEAM, member_count: 1 })
      .mockResolvedValueOnce(MEMBERS)

    renderAt('/admin/teams/t1')
    await waitFor(() => screen.getByText('Alpha'))

    await userEvent.type(
      screen.getByPlaceholderText('teams.detail.addMemberUid'),
      'u-2',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'teams.detail.add' }),
    )

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/teams/t1/members',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('DELETEs a member when remove is clicked', async () => {
    apiFetchMock
      .mockResolvedValueOnce(TEAM)
      .mockResolvedValueOnce(MEMBERS)
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ ...TEAM, member_count: 0 })
      .mockResolvedValueOnce([])

    renderAt('/admin/teams/t1')
    await waitFor(() => screen.getByText('u-1'))

    await userEvent.click(
      screen.getByRole('button', { name: 'teams.detail.remove' }),
    )

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/teams/t1/members/u-1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })
})
