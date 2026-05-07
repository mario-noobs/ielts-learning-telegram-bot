import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import UsersPage from './UsersPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}))

vi.mock('../../components/Pagination', () => ({
  default: () => <div data-testid="pagination" />,
}))

describe('<UsersPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders the rows returned from the API', async () => {
    apiFetchMock.mockResolvedValue({
      items: [
        {
          id: 'u1', name: 'Alice', email: 'a@b.test',
          auth_uid: null, role: 'user', plan: 'free',
          plan_expires_at: null, quota_override: null,
          last_active_date: '2026-05-01', created_at: null,
        },
      ],
      total: 1, page: 1, page_size: 50,
    })
    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument()
    })
    expect(screen.getByText('a@b.test')).toBeInTheDocument()
  })

  it('renders the empty state when no rows match', async () => {
    apiFetchMock.mockResolvedValue({
      items: [], total: 0, page: 1, page_size: 50,
    })
    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText('users.empty')).toBeInTheDocument()
    })
  })

})
