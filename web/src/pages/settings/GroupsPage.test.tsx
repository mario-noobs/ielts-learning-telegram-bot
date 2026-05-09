import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import GroupsPage from './GroupsPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

beforeEach(() => {
  apiFetchMock.mockReset()
})

function render_() {
  return render(
    <MemoryRouter>
      <GroupsPage />
    </MemoryRouter>,
  )
}

describe('<GroupsPage>', () => {
  it('shows empty-state CTA when the user has no groups', async () => {
    apiFetchMock.mockResolvedValueOnce([])
    render_()
    await waitFor(() =>
      expect(screen.getByText('groups.empty.heading')).toBeInTheDocument(),
    )
    expect(
      screen.getByRole('link', { name: /groups\.empty\.cta/ }),
    ).toHaveAttribute('href', '/settings/link-telegram')
  })

  it('renders group cards with role chips and links to detail', async () => {
    apiFetchMock.mockResolvedValueOnce([
      {
        id: '12345',
        name: 'IELTS 7+ Squad',
        member_count: 8,
        role: 'owner',
        default_band: 7.0,
        topics: ['education', 'environment'],
        daily_time: '08:00',
      },
    ])
    render_()
    await waitFor(() =>
      expect(screen.getByText('IELTS 7+ Squad')).toBeInTheDocument(),
    )
    expect(screen.getByText('groups.role.owner')).toBeInTheDocument()
    // Card whole area links to detail
    const detailLink = screen.getByRole('link', { name: /IELTS 7\+ Squad/ })
    expect(detailLink).toHaveAttribute('href', '/settings/groups/12345')
    // Topic chips render up to 3
    expect(screen.getByText('education')).toBeInTheDocument()
    expect(screen.getByText('environment')).toBeInTheDocument()
  })
})
