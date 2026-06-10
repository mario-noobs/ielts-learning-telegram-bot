import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { useMario } from '../hooks/useMario'
import { MARIO_EVENTS_ENDPOINT, MARIO_STATE_ENDPOINT } from './marioTypes'

const apiFetchMock = vi.fn()
vi.mock('./api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

function Harness() {
  const mario = useMario()
  const location = useLocation()
  if (mario.hidden) return <p>hidden</p>
  return (
    <div>
      <p data-testid="route">{location.pathname}</p>
      <p data-testid="panel">{mario.panelOpen ? 'open' : 'closed'}</p>
      <button type="button" onClick={mario.openPanel}>
        open
      </button>
      <button type="button" onClick={mario.dismissSession}>
        dismiss
      </button>
      <button type="button" onClick={mario.optOut}>
        opt out
      </button>
      {mario.actions.map((action) => (
        <button
          key={action.id}
          type="button"
          onClick={() => mario.selectAction(action)}
        >
          {action.label}
        </button>
      ))}
    </div>
  )
}

function renderHarness(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Harness />
    </MemoryRouter>,
  )
}

describe('useMario', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    localStorage.clear()
    sessionStorage.clear()
    apiFetchMock.mockImplementation((path: string) => {
      if (path.startsWith(MARIO_STATE_ENDPOINT)) {
        return Promise.resolve({
          enabled: true,
          persona_name: 'Mario',
          message: 'Keep going',
          action_chips: [
            {
              id: 'write',
              label: 'Write',
              route: '/practice/writing',
              route_patterns: ['/'],
              priority: 1,
            },
            {
              id: 'review',
              label: 'Review',
              route: '/learn/review',
              route_patterns: ['/learn/*'],
              priority: 1,
            },
          ],
          nudge: null,
          highlight: null,
        })
      }
      if (path === MARIO_EVENTS_ENDPOINT) return Promise.resolve(undefined)
      return Promise.reject(new Error(`unexpected path: ${path}`))
    })
  })

  it('starts minimized and opens on request', async () => {
    const user = userEvent.setup()
    renderHarness('/')

    expect(await screen.findByTestId('panel')).toHaveTextContent('closed')
    await user.click(screen.getByRole('button', { name: 'open' }))

    expect(screen.getByTestId('panel')).toHaveTextContent('open')
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        MARIO_EVENTS_ENDPOINT,
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"event":"expanded"'),
        }),
      )
    })
  })

  it('uses route-aware actions and navigates through React Router', async () => {
    const user = userEvent.setup()
    renderHarness('/')

    await screen.findByRole('button', { name: 'Write' })
    expect(screen.queryByRole('button', { name: 'Review' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Write' }))

    expect(screen.getByTestId('route')).toHaveTextContent('/practice/writing')
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        MARIO_EVENTS_ENDPOINT,
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"suggestion_id":"write"'),
        }),
      )
    })
  })

  it('persists session dismissal and opt-out separately', async () => {
    const user = userEvent.setup()
    const { unmount } = renderHarness('/')

    await user.click(await screen.findByRole('button', { name: 'dismiss' }))
    expect(sessionStorage.getItem('mario.v1.session_hidden')).toBe('1')
    expect(localStorage.getItem('mario.v1.opt_out')).toBeNull()
    expect(screen.getByText('hidden')).toBeInTheDocument()

    unmount()
    sessionStorage.clear()
    renderHarness('/')
    await user.click(await screen.findByRole('button', { name: 'opt out' }))
    expect(localStorage.getItem('mario.v1.opt_out')).toBe('1')
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/v1/me',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ dismissed_onboarding: true }),
      }),
    )
  })
})
