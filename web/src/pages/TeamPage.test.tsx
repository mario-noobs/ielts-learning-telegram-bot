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
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

function renderPage() {
  return render(
    <MemoryRouter>
      <TeamPage />
    </MemoryRouter>,
  )
}

describe('<TeamPage>', () => {
  const team = {
    id: 'team-1',
    name: 'Band 7 Crew',
    owner_uid: 'u1',
    plan_id: 'free',
    seat_limit: 5,
    member_count: 2,
    my_role: 'owner',
    created_at: '2026-05-28T00:00:00Z',
  }
  const members = [
    {
      user_id: 'u1',
      name: 'Owner User',
      email: 'owner@example.test',
      role: 'owner',
      joined_at: '2026-05-28T00:00:00Z',
      is_current_user: true,
    },
    {
      user_id: 'u2',
      name: 'Member User',
      email: 'member@example.test',
      role: 'member',
      joined_at: '2026-05-28T00:00:00Z',
      is_current_user: false,
    },
  ]
  const overview = {
    week_start: '2026-05-25T00:00:00Z',
    weekly_active_members: 2,
    study_minutes: 45,
    words_reviewed: 6,
    words_mastered: 2,
    quiz_count: 3,
    member_count: 2,
    seat_limit: 5,
  }
  const memberProgress = {
    week_start: '2026-05-25T00:00:00Z',
    members: [
      {
        user_id: 'u1',
        name: 'Owner User',
        email: 'owner@example.test',
        role: 'owner',
        last_active_date: '2026-05-28',
        weekly_minutes: 30,
        words_reviewed: 4,
        due_words: 1,
        current_streak: 3,
      },
      {
        user_id: 'u2',
        name: 'Member User',
        email: 'member@example.test',
        role: 'member',
        last_active_date: '2026-05-27',
        weekly_minutes: 15,
        words_reviewed: 2,
        due_words: 5,
        current_streak: 1,
      },
    ],
  }

  it('creates a team from the empty state', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team: null })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({ team: { ...team, member_count: 1 } })
      }
      if (url === '/api/v1/teams/team-1/members') {
        return Promise.resolve({ team: { ...team, member_count: 1 }, members: [members[0]] })
      }
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
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
        return Promise.resolve({ team })
      }
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') return Promise.resolve({ team, members })
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
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

  it('highlights roles and renders weekly team overview', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') return Promise.resolve({ team, members })
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    expect(await screen.findByText('Band 7 Crew')).toBeInTheDocument()
    expect(screen.getAllByText('roles.owner').length).toBeGreaterThan(0)
    expect(screen.getAllByText('roles.member').length).toBeGreaterThan(0)
    expect(screen.getByText('overview.activeMembers')).toBeInTheDocument()
    expect(screen.getByText('45')).toBeInTheDocument()
    expect(screen.getByText('progress.title')).toBeInTheDocument()
    expect(screen.getAllByText('Member User').length).toBeGreaterThan(0)
    expect(trackMock).toHaveBeenCalledWith('team_dashboard_viewed', {
      team_id: 'team-1',
      role: 'owner',
      member_count: 2,
    })
  })

  it('lets owners promote and remove members', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') return Promise.resolve({ team, members })
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
      if (url === '/api/v1/teams/team-1/members/u2' && options?.method === 'PATCH') {
        return Promise.resolve({ member: { ...members[1], role: 'admin' } })
      }
      if (url === '/api/v1/teams/team-1/members/u2' && options?.method === 'DELETE') {
        return Promise.resolve(undefined)
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    const roleSelect = await screen.findByLabelText('members.roleActionLabel|{"name":"Member User"}')
    await userEvent.selectOptions(roleSelect, 'admin')
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/teams/team-1/members/u2', {
        method: 'PATCH',
        body: JSON.stringify({ role: 'admin' }),
      })
    })

    await userEvent.click(screen.getByRole('button', { name: 'members.remove' }))
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/teams/team-1/members/u2', {
        method: 'DELETE',
      })
    })
  })

  it('hides admin progress and management actions from regular members', async () => {
    const memberTeam = { ...team, my_role: 'member' as const }
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team: memberTeam })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') {
        return Promise.resolve({ team: memberTeam, members })
      }
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') {
        throw new Error('member progress should not load for regular members')
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    expect(await screen.findByText('Band 7 Crew')).toBeInTheDocument()
    expect(screen.queryByText('progress.title')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'invite.create' })).not.toBeInTheDocument()
  })
})
