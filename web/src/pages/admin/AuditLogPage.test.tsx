import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import AuditLogPage from './AuditLogPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (k: string) => k
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

vi.mock('../../components/Pagination', () => ({
  default: () => <div data-testid="pagination" />,
}))

const ROW = {
  id: 1,
  event_type: 'user.role_granted',
  actor_uid: 'admin-1',
  target_kind: 'user',
  target_id: 'u-1',
  before: null,
  after: null,
  request_id: null,
  created_at: '2026-05-01T12:00:00+00:00',
}

function renderAt(path = '/admin/audit') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuditLogPage />
    </MemoryRouter>,
  )
}

describe('<AuditLogPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders rows returned from the audit API', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/admin/audit/event-types')) {
        return Promise.resolve(['user.role_granted'])
      }
      if (url.startsWith('/api/v1/admin/audit')) {
        return Promise.resolve({
          items: [ROW], total: 1, page: 1, page_size: 50,
        })
      }
      return Promise.resolve(null)
    })

    renderAt()
    await waitFor(() => {
      // 'user.role_granted' also appears in the event-type <option>, so
      // assert on uniquely-identifying cells from the row.
      expect(screen.getByText('admin-1')).toBeInTheDocument()
      expect(screen.getByText('user/u-1')).toBeInTheDocument()
    })
  })

  it('hydrates filter inputs from URL query params', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/admin/audit/event-types')) return Promise.resolve([])
      return Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 })
    })

    renderAt('/admin/audit?actor_uid=admin-1&target_kind=user')
    await waitFor(() => {
      expect(
        (screen.getByPlaceholderText('audit.filters.actorUid') as HTMLInputElement).value,
      ).toBe('admin-1')
      expect(
        (screen.getByPlaceholderText('audit.filters.targetKind') as HTMLInputElement).value,
      ).toBe('user')
    })
  })

  it('passes the typed actor filter to the API on apply', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/admin/audit/event-types')) return Promise.resolve([])
      return Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 })
    })

    renderAt()
    await waitFor(() => screen.getByText('audit.empty'))

    await userEvent.type(
      screen.getByPlaceholderText('audit.filters.actorUid'),
      'admin-1',
    )
    await userEvent.click(screen.getByRole('button', { name: 'audit.filters.apply' }))

    await waitFor(() => {
      const calls = apiFetchMock.mock.calls.map(([u]) => u as string)
      expect(calls.some((u) => u.includes('actor_uid=admin-1'))).toBe(true)
    })
  })

  it('renders the empty state', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/admin/audit/event-types')) return Promise.resolve([])
      return Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 })
    })
    renderAt()
    await waitFor(() => {
      expect(screen.getByText('audit.empty')).toBeInTheDocument()
    })
  })
})
