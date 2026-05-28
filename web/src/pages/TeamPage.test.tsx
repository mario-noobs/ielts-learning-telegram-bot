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
  useAuth: () => ({ profile: { id: 'u1' }, refreshProfile: refreshProfileMock }),
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
  const knowledgePosts = {
    items: [
      {
        id: 'post-1',
        team_id: 'team-1',
        type: 'shared_word',
        category: 'vocabulary',
        title: 'scalability',
        body: 'Useful for Task 2',
        author: { user_id: 'u2', name: 'Member User' },
        word_snapshot: {
          word: 'scalability',
          definition_en: 'ability to grow',
          definition_vi: 'kha nang mo rong',
          ipa: 'skæləbɪlɪti',
          part_of_speech: 'noun',
          example_en: 'The system has scalability.',
          example_vi: '',
          topic: 'technology',
        },
        saved_to_my_words: false,
        existing_word_id: null,
        reply_count: 0,
        helpful_count: 0,
        helpful_by_me: false,
        created_at: '2026-05-28T00:00:00Z',
      },
    ],
    next_cursor: null,
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
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
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
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
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
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    expect(await screen.findByText('Band 7 Crew')).toBeInTheDocument()
    expect(screen.getAllByText('roles.owner').length).toBeGreaterThan(0)
    expect(screen.getAllByText('roles.member').length).toBeGreaterThan(0)
    expect(screen.getByText('overview.activeMembers')).toBeInTheDocument()
    expect(screen.getByText('45')).toBeInTheDocument()
    expect(screen.getByText('progress.title')).toBeInTheDocument()
    expect(screen.getByText('knowledge.title')).toBeInTheDocument()
    expect(screen.getByText('scalability')).toBeInTheDocument()
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
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
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

  it('creates a team knowledge question', async () => {
    const createdPost = {
      id: 'post-question',
      team_id: 'team-1',
      type: 'question',
      category: 'writing',
      title: 'How do I use coherence?',
      body: 'I want a natural Task 2 example.',
      author: { user_id: 'u1', name: 'Owner User' },
      word_snapshot: null,
      saved_to_my_words: false,
      existing_word_id: null,
      reply_count: 0,
      helpful_count: 0,
      helpful_by_me: false,
      created_at: '2026-05-28T00:00:00Z',
    }
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') return Promise.resolve({ team, members })
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
      if (url === '/api/v1/teams/team-1/knowledge/posts') {
        expect(options?.method).toBe('POST')
        expect(JSON.parse(String(options?.body))).toEqual({
          type: 'question',
          category: 'writing',
          title: 'How do I use coherence?',
          body: 'I want a natural Task 2 example.',
        })
        return Promise.resolve({ post: createdPost })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await userEvent.selectOptions(await screen.findByLabelText('knowledge.askCategory'), 'writing')
    await userEvent.type(screen.getByLabelText('knowledge.askTitle'), 'How do I use coherence?')
    await userEvent.type(screen.getByLabelText('knowledge.askBody'), 'I want a natural Task 2 example.')
    await userEvent.click(screen.getByRole('button', { name: 'knowledge.ask' }))

    expect(await screen.findByText('How do I use coherence?')).toBeInTheDocument()
    expect(trackMock).toHaveBeenCalledWith('team_knowledge_question_created', {
      team_id: 'team-1',
      post_id: 'post-question',
    })
  })

  it('loads replies on demand and updates helpful counts', async () => {
    const reply = {
      id: 'reply-1',
      post_id: 'post-1',
      team_id: 'team-1',
      author: { user_id: 'u1', name: 'Owner User' },
      body: 'Use it when describing system growth.',
      helpful_count: 0,
      helpful_by_me: false,
      created_at: '2026-05-28T00:00:00Z',
    }
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') return Promise.resolve({ team, members })
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
      if (url === '/api/v1/teams/team-1/knowledge/posts/post-1/replies?limit=20') {
        return Promise.resolve({ items: [reply], next_cursor: null })
      }
      if (url === '/api/v1/teams/team-1/knowledge/posts/post-1/helpful') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          target_type: 'post',
          target_id: 'post-1',
          helpful_count: 1,
          helpful_by_me: true,
        })
      }
      if (url === '/api/v1/teams/team-1/knowledge/posts/post-1/replies') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          reply: {
            ...reply,
            id: 'reply-2',
            body: 'I would use it in technology essays.',
          },
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: /knowledge\.replies/ }))
    expect(await screen.findByText('Use it when describing system growth.')).toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('button', { name: /knowledge\.helpful/ })[0])
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'knowledge.helpful|{"count":1}' }))
        .toBeInTheDocument()
    })

    await userEvent.type(screen.getByPlaceholderText('knowledge.replyPlaceholder'), 'I would use it in technology essays.')
    await userEvent.click(screen.getByRole('button', { name: 'knowledge.reply' }))
    expect(await screen.findByText('I would use it in technology essays.')).toBeInTheDocument()
  })

  it('lets admins delete team knowledge posts and replies', async () => {
    const reply = {
      id: 'reply-1',
      post_id: 'post-1',
      team_id: 'team-1',
      author: { user_id: 'u2', name: 'Member User' },
      body: 'This should be moderated.',
      helpful_count: 0,
      helpful_by_me: false,
      created_at: '2026-05-28T00:00:00Z',
    }
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/teams/me') return Promise.resolve({ team })
      if (url === '/api/v1/teams/team-1/views') return Promise.resolve({})
      if (url === '/api/v1/teams/team-1/members') return Promise.resolve({ team, members })
      if (url === '/api/v1/teams/team-1/overview') return Promise.resolve(overview)
      if (url === '/api/v1/teams/team-1/member-progress') return Promise.resolve(memberProgress)
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') {
        return Promise.resolve({
          ...knowledgePosts,
          items: [{ ...knowledgePosts.items[0], reply_count: 1 }],
        })
      }
      if (url === '/api/v1/teams/team-1/knowledge/posts/post-1/replies?limit=20') {
        return Promise.resolve({ items: [reply], next_cursor: null })
      }
      if (url === '/api/v1/teams/team-1/knowledge/posts/post-1/replies/reply-1') {
        expect(options?.method).toBe('DELETE')
        return Promise.resolve(undefined)
      }
      if (url === '/api/v1/teams/team-1/knowledge/posts/post-1') {
        expect(options?.method).toBe('DELETE')
        return Promise.resolve(undefined)
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'knowledge.replies|{"count":1}' }))
    expect(await screen.findByText('This should be moderated.')).toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('button', { name: 'knowledge.delete' })[1])
    await waitFor(() => {
      expect(screen.queryByText('This should be moderated.')).not.toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: 'knowledge.delete' }))
    await waitFor(() => {
      expect(screen.queryByText('scalability')).not.toBeInTheDocument()
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
      if (url === '/api/v1/teams/team-1/knowledge/posts?limit=10') return Promise.resolve(knowledgePosts)
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
