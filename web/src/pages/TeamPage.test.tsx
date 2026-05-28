import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import TeamPage from './TeamPage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const refreshProfileMock = vi.fn()
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ refreshProfile: refreshProfileMock }),
}))

const trackMock = vi.fn()
vi.mock('../lib/analytics', () => ({
  track: (...args: unknown[]) => trackMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

beforeEach(() => {
  apiFetchMock.mockReset()
  refreshProfileMock.mockReset()
  trackMock.mockReset()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <TeamPage />
    </MemoryRouter>,
  )
}

describe('<TeamPage>', () => {
  it('creates a team from the empty state', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team: null })
      if (url === '/api/v1/teams') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          team: {
            id: 'team-1',
            name: 'Band 7 Crew',
            owner_uid: 'u1',
            plan_id: 'free',
            seat_limit: 5,
            member_count: 1,
            my_role: 'owner',
            created_at: '2026-05-28T00:00:00Z',
          },
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await userEvent.type(await screen.findByLabelText('create.nameLabel'), 'Band 7 Crew')
    await userEvent.click(screen.getByRole('button', { name: 'create.submit' }))

    expect(await screen.findByText('Band 7 Crew')).toBeInTheDocument()
    expect(refreshProfileMock).toHaveBeenCalled()
    expect(trackMock).toHaveBeenCalledWith('team_created', { team_id: 'team-1' })
  })

  it('creates and displays an invite link for admins', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') {
        return Promise.resolve({
          team: {
            id: 'team-1',
            name: 'Band 7 Crew',
            owner_uid: 'u1',
            plan_id: 'free',
            seat_limit: 5,
            member_count: 1,
            my_role: 'owner',
            created_at: '2026-05-28T00:00:00Z',
          },
        })
      }
      if (url === '/api/v1/teams/team-1/invites') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          token: 'invite-token',
          invite_url: '/team/invite/invite-token',
          expires_at: '2026-06-04T00:00:00Z',
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'invite.create' }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('http://localhost:3000/team/invite/invite-token'))
        .toBeInTheDocument()
    })
    expect(trackMock).toHaveBeenCalledWith('team_invite_created', { team_id: 'team-1' })
  })
})
