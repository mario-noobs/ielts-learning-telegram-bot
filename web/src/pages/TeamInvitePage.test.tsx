import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import TeamInvitePage from './TeamInvitePage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

let profileMock: unknown = null
const refreshProfileMock = vi.fn()
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    profile: profileMock,
    loading: false,
    refreshProfile: refreshProfileMock,
  }),
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
  profileMock = null
})

function renderAt(path = '/team/invite/invite-token') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/team/invite/:token" element={<TeamInvitePage />} />
        <Route path="/team" element={<div>Team workspace</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

const preview = {
  team_id: 'team-1',
  team_name: 'Band 7 Crew',
  expires_at: '2026-06-04T00:00:00Z',
  member_count: 1,
  seat_limit: 5,
  already_member: false,
}

describe('<TeamInvitePage>', () => {
  it('prompts logged-out users to sign in and preserves invite path', async () => {
    apiFetchMock.mockResolvedValue(preview)

    renderAt()

    const link = await screen.findByRole('link', { name: 'join.signIn' })
    expect(link).toHaveAttribute('href', '/login?next=%2Fteam%2Finvite%2Finvite-token')
  })

  it('accepts an invite for logged-in users', async () => {
    profileMock = { id: 'u1' }
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/invites/invite-token') return Promise.resolve(preview)
      if (url === '/api/v1/teams/invites/invite-token/accept') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({ team: { id: 'team-1', name: 'Band 7 Crew', my_role: 'member' } })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderAt()

    await userEvent.click(await screen.findByRole('button', { name: 'join.accept' }))

    expect(await screen.findByText('join.success')).toBeInTheDocument()
    expect(refreshProfileMock).toHaveBeenCalled()
    expect(trackMock).toHaveBeenCalledWith('team_invite_accepted', { team_id: 'team-1' })
  })
})
