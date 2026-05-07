import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth, useProfile } from '../contexts/AuthContext'

/**
 * Wraps the `/admin/*` route subtree. Behavior:
 *
 * - While auth state is still loading: render nothing (avoids a flash
 *   of redirect for legitimate admins on a slow connection).
 * - Not signed in: redirect to /login (so the user can come back).
 * - Signed in but not an admin: redirect to / (no breadcrumb leak).
 * - Signed in and `role !== 'user'`: render children.
 *
 * The role check intentionally accepts any non-`user` role so team_admin
 * and org_admin can reach the team/org sections that ship in M11.4.
 * Individual route handlers tighten further when they need to.
 */
export default function AdminGate({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const profile = useProfile()
  const location = useLocation()

  if (loading) return null

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (!profile || profile.role === 'user') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
