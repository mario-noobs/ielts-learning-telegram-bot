import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  type User,
  getRedirectResult,
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from 'firebase/auth'
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
  signInWithGoogle: (options?: { redirect?: boolean }) => Promise<void>
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
  // Prevents onAuthStateChanged from re-fetching profile mid auth transitions,
  // which would race against setProfile(null) and restore the previous session.
  const authTransitionRef = useRef(false)
  const profileRequestRef = useRef(0)

  const fetchProfile = useCallback(async ({ rethrow = false } = {}) => {
    const requestId = ++profileRequestRef.current
    try {
      const me = await apiFetch<unknown>('/api/v1/me')
      if (requestId === profileRequestRef.current) setProfile(normalize(me))
    } catch (err) {
      if (requestId === profileRequestRef.current) setProfile(null)
      if (rethrow) throw err
    }
  }, [])

  const clearLocalSession = useCallback(async () => {
    try {
      await apiFetch('/api/v1/auth/local/logout', { method: 'POST' })
    } catch {
      // Best-effort cleanup. The next API request will still prefer Bearer auth.
    }
  }, [])

  const beginAuthTransition = () => {
    authTransitionRef.current = true
    profileRequestRef.current += 1
    setProfile(null)
  }

  const endAuthTransition = () => {
    authTransitionRef.current = false
    setLoading(false)
  }

  useEffect(() => {
    let cancelled = false
    let authSettled = false
    let redirectSettled = false
    let pendingUser: User | null = null

    const finishInitialAuth = async () => {
      if (!authSettled || !redirectSettled || authTransitionRef.current) return
      setUser(pendingUser)
      // Always attempt profile fetch — works for Firebase Bearer (when u is set)
      // and for local auth via httpOnly cookie (when u is null).
      await fetchProfile()
      if (!cancelled) setLoading(false)
    }

    const unsubscribe = onAuthStateChanged(auth, async (u) => {
      if (authTransitionRef.current) return
      authSettled = true
      pendingUser = u
      await finishInitialAuth()
    })

    void getRedirectResult(auth)
      .then(async (result) => {
        redirectSettled = true
        if (result?.user) pendingUser = result.user
        await finishInitialAuth()
      })
      .catch(async () => {
        redirectSettled = true
        await finishInitialAuth()
      })

    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [fetchProfile])

  const signInWithGoogle = async (options?: { redirect?: boolean }) => {
    beginAuthTransition()
    try {
      await clearLocalSession()
      if (options?.redirect) {
        await signInWithRedirect(auth, googleProvider)
        return
      }
      const result = await signInWithPopup(auth, googleProvider)
      setUser(result.user)
      await fetchProfile({ rethrow: true })
    } finally {
      endAuthTransition()
    }
  }

  const signInLocal = async (email: string, password: string) => {
    beginAuthTransition()
    setUser(null)
    try {
      if (auth.currentUser) await signOut(auth)
      await clearLocalSession()
      await apiFetch('/api/v1/auth/local/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      await fetchProfile({ rethrow: true })
    } finally {
      endAuthTransition()
    }
  }

  const registerLocal = async (data: LocalRegisterData) => {
    beginAuthTransition()
    setUser(null)
    try {
      if (auth.currentUser) await signOut(auth)
      await clearLocalSession()
      await apiFetch('/api/v1/auth/local/register', {
        method: 'POST',
        body: JSON.stringify(data),
      })
      await fetchProfile({ rethrow: true })
    } finally {
      endAuthTransition()
    }
  }

  const logout = async () => {
    beginAuthTransition()
    setUser(null)
    setProfile(null)
    try {
      // Always try to clear server-side session cookie, regardless of auth method.
      // For Firebase-only users this is a no-op; for local auth it revokes the cookie.
      await clearLocalSession()
      if (auth.currentUser) await signOut(auth)
    } catch {
      // Client state is already cleared; keep logout deterministic for the UI.
    } finally {
      setUser(null)
      setProfile(null)
      endAuthTransition()
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
