import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import OrgDetailPage from './OrgDetailPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string) => k
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

const ORG = {
  id: 'o1', name: 'Acme', owner_uid: 'u-a',
  plan_id: 'org_member', plan_expires_at: null,
  created_at: null, admin_count: 1, team_count: 1,
}
const ADMINS = ['u-1']
const TEAMS = ['t-1']

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/orgs/:id" element={<OrgDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<OrgDetailPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders org header, admins, and team links', async () => {
    apiFetchMock
      .mockResolvedValueOnce(ORG)     // GET /orgs/:id
      .mockResolvedValueOnce(ADMINS)  // GET /orgs/:id/admins
      .mockResolvedValueOnce(TEAMS)   // GET /orgs/:id/teams

    renderAt('/admin/orgs/o1')
    await waitFor(() => {
      expect(screen.getByText('Acme')).toBeInTheDocument()
      expect(screen.getByText('u-1')).toBeInTheDocument()
      expect(screen.getByText('t-1')).toBeInTheDocument()
    })
  })

  it('POSTs a new admin when the add-admin form is submitted', async () => {
    apiFetchMock
      .mockResolvedValueOnce(ORG)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(TEAMS)
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce(ORG)
      .mockResolvedValueOnce(ADMINS)
      .mockResolvedValueOnce(TEAMS)

    renderAt('/admin/orgs/o1')
    await waitFor(() => screen.getByText('Acme'))

    await userEvent.type(
      screen.getByPlaceholderText('orgs.detail.addAdminUid'),
      'u-2',
    )
    // The "add" label is reused for the link team button too — pick the
    // first match (admins section comes before teams section).
    const addButtons = screen.getAllByRole('button', { name: 'orgs.detail.add' })
    await userEvent.click(addButtons[0])

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/orgs/o1/admins',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('POSTs a team-link when the link form is submitted', async () => {
    apiFetchMock
      .mockResolvedValueOnce(ORG)
      .mockResolvedValueOnce(ADMINS)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce(ORG)
      .mockResolvedValueOnce(ADMINS)
      .mockResolvedValueOnce(TEAMS)

    renderAt('/admin/orgs/o1')
    await waitFor(() => screen.getByText('Acme'))

    await userEvent.type(
      screen.getByPlaceholderText('orgs.detail.linkTeamId'),
      't-1',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'orgs.detail.link' }),
    )

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/orgs/o1/teams',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
})
