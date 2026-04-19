import { parseApiError } from './apiError'
import { auth } from './firebase'

const API_URL = import.meta.env.VITE_API_URL || ''

async function getToken(): Promise<string | null> {
  const user = auth.currentUser
  if (!user) return null
  return user.getIdToken()
}

/**
 * Fetch wrapper that throws an `ApiError` on non-2xx responses (US-M7.3).
 *
 * Callers that want to show the message to the user should catch the
 * ApiError and call `.localize()`. Callers that only need .message for
 * legacy string-based error rendering still work — ApiError extends Error
 * and its `.message` is the error code (not the prose). Migrate call sites
 * to `.localize()` as you touch them.
 */
export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) {
    const raw = await res.json().catch(() => null)
    throw parseApiError(raw, res.status)
  }
  return res.json()
}
