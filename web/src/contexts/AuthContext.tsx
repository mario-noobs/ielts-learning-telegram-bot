import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { type User, onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth'
import { apiFetch } from '../lib/api'
import { auth, googleProvider } from '../lib/firebase'

/**
 * Backend user profile shape from `GET /api/v1/me`.
 *
 * Admin fields default to `'user'` / `'free'` when the API returns them
 * unset (pre-M8.2-cutover Firestore data lacks them; M11.1's UserDoc
 * defaults take over post-cutover).
 */
export interface BackendProfile {
  id: string
  name: string
  email?: string | null
  target_band?: number
  preferred_locale?: 'en' | 'vi' | null
  // Admin fields (M11.1 schema, M11.2 DTO).
  role: 'user' | 'team_admin' | 'org_admin' | 'platform_admin'
  plan: string
  team_id?: string | null
  org_id?: string | null
  quota_override?: number | null
}

interface AuthContextType {
  user: User | null
  profile: BackendProfile | null
  loading: boolean
  signInWithGoogle: () => Promise<void>
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

function normalize(raw: unknown): BackendProfile | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Record<string, unknown>
  if (typeof r.id !== 'string') return null
  return {
    id: r.id,
    name: typeof r.name === 'string' ? r.name : '',
    email: (r.email as string | null | undefined) ?? null,
    target_band: typeof r.target_band === 'number' ? r.target_band : undefined,
    preferred_locale: (r.preferred_locale as 'en' | 'vi' | null | undefined) ?? null,
    role: (r.role as BackendProfile['role']) || 'user',
    plan: typeof r.plan === 'string' ? r.plan : 'free',
    team_id: (r.team_id as string | null | undefined) ?? null,
    org_id: (r.org_id as string | null | undefined) ?? null,
    quota_override:
      typeof r.quota_override === 'number' ? r.quota_override : null,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<BackendProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchProfile = useCallback(async () => {
    try {
      const me = await apiFetch<unknown>('/api/v1/me')
      setProfile(normalize(me))
    } catch {
      // Profile not available (404 first-time signup, or transient).
      // Components fall back to `null` and gate accordingly.
      setProfile(null)
    }
  }, [])

  useEffect(() => {
    return onAuthStateChanged(auth, async (u) => {
      setUser(u)
      if (u) {
        await fetchProfile()
      } else {
        setProfile(null)
      }
      setLoading(false)
    })
  }, [fetchProfile])

  const signInWithGoogle = async () => {
    await signInWithPopup(auth, googleProvider)
  }

  const logout = async () => {
    await signOut(auth)
    setProfile(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        signInWithGoogle,
        logout,
        refreshProfile: fetchProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

/**
 * Subset of the backend profile most components actually need.
 * Returns `null` while the profile is still loading or when the user
 * isn't signed in.
 */
export function useProfile(): BackendProfile | null {
  return useContext(AuthContext)?.profile ?? null
}
