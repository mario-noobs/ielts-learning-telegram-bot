import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'

const mocks = vi.hoisted(() => ({
  auth: { currentUser: null as null | { uid: string; email?: string } },
  apiFetch: vi.fn(),
  onAuthStateChanged: vi.fn(),
  signInWithPopup: vi.fn(),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
  authStateHandler: null as null | ((user: unknown) => void | Promise<void>),
}))

vi.mock('../lib/firebase', () => ({
  auth: mocks.auth,
  googleProvider: { providerId: 'google.com' },
}))

vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mocks.apiFetch(...args),
}))

vi.mock('firebase/auth', () => ({
  onAuthStateChanged: (...args: unknown[]) => mocks.onAuthStateChanged(...args),
  signInWithPopup: (...args: unknown[]) => mocks.signInWithPopup(...args),
  signInWithRedirect: (...args: unknown[]) => mocks.signInWithRedirect(...args),
  signOut: (...args: unknown[]) => mocks.signOut(...args),
}))

function profilePayload(id: string) {
  return {
    id,
    name: id,
    role: 'user',
    plan: 'free',
  }
}

function Harness() {
  const auth = useAuth()
  return (
    <div>
      <p data-testid="profile">{auth.profile?.id ?? 'none'}</p>
      <button type="button" onClick={() => void auth.signInLocal('local@test.dev', 'password')}>
        local
      </button>
      <button type="button" onClick={() => void auth.signInWithGoogle()}>
        google
      </button>
      <button type="button" onClick={() => void auth.signInWithGoogle({ redirect: true })}>
        google redirect
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        logout
      </button>
    </div>
  )
}

function renderAuth() {
  return render(
    <AuthProvider>
      <Harness />
    </AuthProvider>,
  )
}

beforeEach(() => {
  mocks.auth.currentUser = null
  mocks.authStateHandler = null
  mocks.apiFetch.mockReset()
  mocks.signInWithPopup.mockReset()
  mocks.signInWithRedirect.mockReset()
  mocks.signOut.mockReset()
  mocks.onAuthStateChanged.mockReset()
  mocks.onAuthStateChanged.mockImplementation((_auth, callback) => {
    mocks.authStateHandler = callback as typeof mocks.authStateHandler
    return vi.fn()
  })
  mocks.signOut.mockImplementation(async () => {
    mocks.auth.currentUser = null
  })
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('<AuthProvider>', () => {
  it('signs out Firebase before starting a local login', async () => {
    mocks.auth.currentUser = { uid: 'google-old', email: 'old@test.dev' }
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/auth/local/logout') return Promise.resolve(undefined)
      if (path === '/api/v1/auth/local/login') return Promise.resolve({})
      if (path === '/api/v1/me') return Promise.resolve(profilePayload('local-new'))
      throw new Error(`Unexpected API call: ${path}`)
    })

    renderAuth()
    await userEvent.click(screen.getByRole('button', { name: 'local' }))

    await waitFor(() => expect(screen.getByTestId('profile')).toHaveTextContent('local-new'))
    expect(mocks.signOut).toHaveBeenCalledTimes(1)
    expect(mocks.apiFetch.mock.calls[0][0]).toBe('/api/v1/auth/local/logout')
    expect(mocks.apiFetch.mock.calls[1][0]).toBe('/api/v1/auth/local/login')
  })

  it('clears local cookies before starting a Google popup login', async () => {
    const googleUser = { uid: 'google-new', email: 'new@test.dev' }
    mocks.signInWithPopup.mockImplementation(async () => {
      mocks.auth.currentUser = googleUser
      return { user: googleUser }
    })
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/auth/local/logout') return Promise.resolve(undefined)
      if (path === '/api/v1/me') return Promise.resolve(profilePayload('google-new'))
      throw new Error(`Unexpected API call: ${path}`)
    })

    renderAuth()
    await userEvent.click(screen.getByRole('button', { name: 'google' }))

    await waitFor(() => expect(screen.getByTestId('profile')).toHaveTextContent('google-new'))
    expect(mocks.apiFetch.mock.calls[0][0]).toBe('/api/v1/auth/local/logout')
    expect(mocks.signInWithPopup).toHaveBeenCalledTimes(1)
  })

  it('uses redirect login when requested for mobile browsers', async () => {
    mocks.signInWithRedirect.mockResolvedValue(undefined)
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/auth/local/logout') return Promise.resolve(undefined)
      throw new Error(`Unexpected API call: ${path}`)
    })

    renderAuth()
    await userEvent.click(screen.getByRole('button', { name: 'google redirect' }))

    expect(mocks.apiFetch.mock.calls[0][0]).toBe('/api/v1/auth/local/logout')
    expect(mocks.signInWithRedirect).toHaveBeenCalledTimes(1)
    expect(mocks.signInWithPopup).not.toHaveBeenCalled()
  })

  it('clears client state even when logout cleanup fails', async () => {
    const googleUser = { uid: 'google-old', email: 'old@test.dev' }
    mocks.auth.currentUser = googleUser
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path === '/api/v1/me') return Promise.resolve(profilePayload('google-old'))
      if (path === '/api/v1/auth/local/logout') return Promise.reject(new Error('offline'))
      throw new Error(`Unexpected API call: ${path}`)
    })
    mocks.signOut.mockRejectedValue(new Error('firebase unavailable'))

    renderAuth()
    await act(async () => {
      await mocks.authStateHandler?.(googleUser)
    })
    await screen.findByText('google-old')

    await userEvent.click(screen.getByRole('button', { name: 'logout' }))

    await waitFor(() => expect(screen.getByTestId('profile')).toHaveTextContent('none'))
  })
})
