import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import LinkRedeemPage from './LinkRedeemPage'

const useAuthMock = vi.fn()

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      // Echo params into the string so assertions can probe substitution.
      if (!params) return key
      const fragments = Object.entries(params).map(([k, v]) => `${k}=${v}`).join(',')
      return `${key}:${fragments}`
    },
  }),
}))

const redeemMock = vi.fn()
vi.mock('../lib/link', async () => {
  const actual = await vi.importActual<typeof import('../lib/link')>('../lib/link')
  return {
    ...actual,
    redeemLink: (...args: unknown[]) => redeemMock(...(args as [string])),
  }
})

beforeEach(() => {
  redeemMock.mockReset()
})

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/link${search}`]}>
      <Routes>
        <Route path="/" element={<div>home</div>} />
        <Route path="/link" element={<LinkRedeemPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<LinkRedeemPage>', () => {
  it('shows a missing-token error when ?token is absent', () => {
    useAuthMock.mockReturnValue({
      user: null,
      loading: false,
      signInWithGoogle: vi.fn(),
      refreshProfile: vi.fn(),
    })
    renderAt('')
    expect(screen.getByText('redeem.error.missingToken.title')).toBeInTheDocument()
  })

  it('prompts Google sign-in when the user is signed out but the token is present', () => {
    const signIn = vi.fn()
    useAuthMock.mockReturnValue({
      user: null,
      loading: false,
      signInWithGoogle: signIn,
      refreshProfile: vi.fn(),
    })
    renderAt('?token=abc123')
    expect(screen.getByText('redeem.signInRequired.title')).toBeInTheDocument()
  })

  it('renders the linked success state on status="linked"', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    useAuthMock.mockReturnValue({
      user: { uid: 'auth-1' },
      loading: false,
      signInWithGoogle: vi.fn(),
      refreshProfile: refresh,
    })
    redeemMock.mockResolvedValue({
      status: 'linked',
      profile: { id: '4242', name: 'U', target_band: 7, topics: [] },
      counts: null,
    })
    renderAt('?token=abc123')
    await waitFor(() => {
      expect(redeemMock).toHaveBeenCalledWith('abc123')
    })
    await waitFor(() => {
      expect(screen.getByText('redeem.success.linked.title')).toBeInTheDocument()
    })
    expect(refresh).toHaveBeenCalled()
  })

  it('renders the merged success state with counts substituted', async () => {
    useAuthMock.mockReturnValue({
      user: { uid: 'auth-1' },
      loading: false,
      signInWithGoogle: vi.fn(),
      refreshProfile: vi.fn().mockResolvedValue(undefined),
    })
    redeemMock.mockResolvedValue({
      status: 'merged',
      profile: { id: '4242', name: 'U', target_band: 7, topics: [] },
      counts: {
        vocab_merged: 5,
        vocab_dropped: 0,
        quiz_merged: 8,
        writing_merged: 0,
        daily_merged: 0,
        daily_skipped: 0,
      },
    })
    renderAt('?token=abc123')
    await waitFor(() => {
      // The mocked t() echoes params, so we can assert vocab/quiz substitution.
      expect(
        screen.getByText('redeem.success.merged.description:vocab=5,quiz=8'),
      ).toBeInTheDocument()
    })
  })

  it('renders the expired error when API returns auth.link.token_expired', async () => {
    useAuthMock.mockReturnValue({
      user: { uid: 'auth-1' },
      loading: false,
      signInWithGoogle: vi.fn(),
      refreshProfile: vi.fn().mockResolvedValue(undefined),
    })
    const { ApiError } = await import('../lib/apiError')
    redeemMock.mockRejectedValue(new ApiError({
      code: 'auth.link.token_expired', http_status: 410, params: {},
    }))
    renderAt('?token=abc123')
    await waitFor(() => {
      expect(screen.getByText('redeem.error.expired.title')).toBeInTheDocument()
    })
  })

  it('navigates to / when "Go to dashboard" is clicked on success', async () => {
    useAuthMock.mockReturnValue({
      user: { uid: 'auth-1' },
      loading: false,
      signInWithGoogle: vi.fn(),
      refreshProfile: vi.fn().mockResolvedValue(undefined),
    })
    redeemMock.mockResolvedValue({
      status: 'linked',
      profile: { id: '4242', name: 'U', target_band: 7, topics: [] },
      counts: null,
    })
    renderAt('?token=abc123')
    await waitFor(() => {
      expect(screen.getByText('redeem.success.linked.title')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('redeem.success.linked.cta'))
    await waitFor(() => {
      expect(screen.getByText('home')).toBeInTheDocument()
    })
  })
})
