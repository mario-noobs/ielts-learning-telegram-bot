import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AdminGate from './AdminGate'

const useAuthMock = vi.fn()
const useProfileMock = vi.fn()

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
  useProfile: () => useProfileMock(),
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>login</div>} />
        <Route path="/" element={<div>home</div>} />
        <Route
          path="/admin"
          element={
            <AdminGate>
              <div>admin-console</div>
            </AdminGate>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<AdminGate>', () => {
  it('renders nothing while auth is still loading', () => {
    useAuthMock.mockReturnValue({ user: null, loading: true })
    useProfileMock.mockReturnValue(null)
    const { container } = renderAt('/admin')
    expect(container).toBeEmptyDOMElement()
  })

  it('redirects to /login when signed out', () => {
    useAuthMock.mockReturnValue({ user: null, loading: false })
    useProfileMock.mockReturnValue(null)
    renderAt('/admin')
    expect(screen.getByText('login')).toBeInTheDocument()
  })

  it('redirects to / for signed-in user with role=user', () => {
    useAuthMock.mockReturnValue({ user: { uid: 'x' }, loading: false })
    useProfileMock.mockReturnValue({ id: 'x', name: '', plan: 'free', role: 'user' })
    renderAt('/admin')
    expect(screen.getByText('home')).toBeInTheDocument()
  })

  it('renders children when role is platform_admin', () => {
    useAuthMock.mockReturnValue({ user: { uid: 'x' }, loading: false })
    useProfileMock.mockReturnValue({
      id: 'x', name: '', plan: 'free', role: 'platform_admin',
    })
    renderAt('/admin')
    expect(screen.getByText('admin-console')).toBeInTheDocument()
  })

  it('renders children when role is team_admin', () => {
    useAuthMock.mockReturnValue({ user: { uid: 'x' }, loading: false })
    useProfileMock.mockReturnValue({
      id: 'x', name: '', plan: 'free', role: 'team_admin',
    })
    renderAt('/admin')
    expect(screen.getByText('admin-console')).toBeInTheDocument()
  })
})
