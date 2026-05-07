import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import OrgsPage from './OrgsPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string) => k
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

const ORGS_PAYLOAD = [
  {
    id: 'o1', name: 'Acme', owner_uid: 'u-a',
    plan_id: 'org_member', plan_expires_at: null,
    created_at: null, admin_count: 1, team_count: 2,
  },
]

describe('<OrgsPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders rows returned from the API', async () => {
    apiFetchMock.mockResolvedValueOnce(ORGS_PAYLOAD)
    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText('Acme')).toBeInTheDocument()
    })
    // 'org_member' also appears in the create-form <select>, so use
    // the admin_count cell as a row-presence check.
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('renders the empty state', async () => {
    apiFetchMock.mockResolvedValueOnce([])
    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText('orgs.empty')).toBeInTheDocument()
    })
  })

  it('POSTs to /admin/orgs when the create form is submitted', async () => {
    apiFetchMock
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ ok: true, extra: { id: 'o1' } })
      .mockResolvedValueOnce(ORGS_PAYLOAD)
    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>,
    )
    await waitFor(() => screen.getByText('orgs.empty'))

    await userEvent.type(
      screen.getByPlaceholderText('orgs.form.name'),
      'Acme',
    )
    await userEvent.type(
      screen.getByPlaceholderText('orgs.form.ownerUid'),
      'u-a',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'orgs.form.create' }),
    )

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/orgs',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
})
