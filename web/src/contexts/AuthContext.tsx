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

export interface BackendProfile {
  id: string
  name: string
  email?: string | null
  target_band?: number
  preferred_locale?: 'en' | 'vi' | null
  role: 'user' | 'team_admin' | 'org_admin' | 'platform_admin'
  plan: string
  team_id?: string | null
  org_id?: string | null
  quota_override?: number | null
  daily_words_count?: number
  dismissed_onboarding?: boolean
  target_band_set?: boolean
  weekly_goal_set?: boolean
}

export interface LocalRegisterData {
  email: string
  username: string
  password: string
  confirm_password: string
  phone?: string
  address?: string
}

interface AuthContextType {
  user: User | null
  profile: BackendProfile | null
  loading: boolean
  signInWithGoogle: () => Promise<void>
  signInLocal: (email: string, password: string) => Promise<void>
  registerLocal: (data: LocalRegisterData) => Promise<void>
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
    daily_words_count:
      typeof r.daily_words_count === 'number' ? r.daily_words_count : undefined,
    dismissed_onboarding:
      typeof r.dismissed_onboarding === 'boolean'
        ? r.dismissed_onboarding
        : undefined,
    target_band_set:
      typeof r.target_band_set === 'boolean' ? r.target_band_set : undefined,
    weekly_goal_set:
      typeof r.weekly_goal_set === 'boolean' ? r.weekly_goal_set : undefined,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<BackendProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchProfile = useCallback(async ({ rethrow = false } = {}) => {
    try {
      const me = await apiFetch<unknown>('/api/v1/me')
      setProfile(normalize(me))
    } catch (err) {
      setProfile(null)
      if (rethrow) throw err
    }
  }, [])

  useEffect(() => {
    return onAuthStateChanged(auth, async (u) => {
      setUser(u)
      // Always attempt profile fetch — works for Firebase Bearer (when u is set)
      // and for local auth via httpOnly cookie (when u is null).
      await fetchProfile()
      setLoading(false)
    })
  }, [fetchProfile])

  const signInWithGoogle = async () => {
    await signInWithPopup(auth, googleProvider)
    // onAuthStateChanged fires and fetches profile
  }

  const signInLocal = async (email: string, password: string) => {
    await apiFetch('/api/v1/auth/local/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    await fetchProfile({ rethrow: true })
  }

  const registerLocal = async (data: LocalRegisterData) => {
    await apiFetch('/api/v1/auth/local/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
    await fetchProfile({ rethrow: true })
  }

  const logout = async () => {
    if (!user && profile) {
      // Local auth session — clear server-side cookie
      try {
        await apiFetch('/api/v1/auth/local/logout', { method: 'POST' })
      } catch { /* best-effort */ }
      setProfile(null)
    } else {
      await signOut(auth)
      setProfile(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        signInWithGoogle,
        signInLocal,
        registerLocal,
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

export function useProfile(): BackendProfile | null {
  return useContext(AuthContext)?.profile ?? null
}
