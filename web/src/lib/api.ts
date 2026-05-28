import { parseApiError } from './apiError'
import { auth } from './firebase'
import {
  clearLocalTokens,
  getLocalAccessToken,
  getLocalRefreshToken,
  setLocalTokens,
} from './localAuth'

const API_URL = import.meta.env.VITE_API_URL || ''

async function getToken(): Promise<string | null> {
  const user = auth.currentUser
  if (user) return user.getIdToken()
  return getLocalAccessToken()
}

interface LocalRefreshResponse {
  access_token?: string | null
  refresh_token?: string | null
}

async function refreshLocalToken(): Promise<string | null> {
  const refreshToken = getLocalRefreshToken()
  if (!refreshToken) return null

  const res = await fetch(`${API_URL}/api/v1/auth/local/refresh`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) {
    clearLocalTokens()
    return null
  }
  const body = (await res.json().catch(() => null)) as LocalRefreshResponse | null
  if (!body?.access_token || !body.refresh_token) {
    clearLocalTokens()
    return null
  }
  setLocalTokens({
    access_token: body.access_token,
    refresh_token: body.refresh_token,
  })
  return body.access_token
}

function shouldTryLocalRefresh(path: string): boolean {
  return Boolean(
    !auth.currentUser
    && getLocalRefreshToken()
    && !path.startsWith('/api/v1/auth/local/'),
  )
}

async function request(path: string, options: RequestInit, token: string | null): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
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
  let res = await request(path, options, await getToken())
  if (res.status === 401 && shouldTryLocalRefresh(path)) {
    const refreshed = await refreshLocalToken()
    if (refreshed) res = await request(path, options, refreshed)
  }
  if (!res.ok) {
    const raw = await res.json().catch(() => null)
    const err = parseApiError(raw, res.status)
    // US-M13.3: surface quota saturation globally so any mounted
    // <QuotaExceededModal> can subscribe via a window event listener.
    if (err.code === 'quota.daily_exceeded' && typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('quota:exceeded', { detail: err.params }),
      )
    }
    throw err
  }
  if (res.status === 204) {
    return undefined as T
  }
  const text = await res.text()
  if (!text) {
    return undefined as T
  }
  return JSON.parse(text) as T
}

/**
 * Like apiFetch but returns the raw Response for streaming (SSE / NDJSON).
 * Throws ApiError on non-2xx, same as apiFetch.
 */
export async function apiStream(path: string, options: RequestInit = {}): Promise<Response> {
  let res = await request(path, options, await getToken())
  if (res.status === 401 && shouldTryLocalRefresh(path)) {
    const refreshed = await refreshLocalToken()
    if (refreshed) res = await request(path, options, refreshed)
  }
  if (!res.ok) {
    const raw = await res.json().catch(() => null)
    throw parseApiError(raw, res.status)
  }
  return res
}
