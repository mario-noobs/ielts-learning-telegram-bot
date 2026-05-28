const ACCESS_KEY = 'ielts.localAuth.accessToken'
const REFRESH_KEY = 'ielts.localAuth.refreshToken'

let memoryAccessToken: string | null = null
let memoryRefreshToken: string | null = null

function storage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    const testKey = 'ielts.localAuth.storageTest'
    window.localStorage.setItem(testKey, '1')
    window.localStorage.removeItem(testKey)
    return window.localStorage
  } catch {
    return null
  }
}

function read(key: string, fallback: string | null): string | null {
  const s = storage()
  if (!s) return fallback
  return s.getItem(key)
}

function write(key: string, value: string | null): void {
  const s = storage()
  if (!s) return
  if (value) s.setItem(key, value)
  else s.removeItem(key)
}

export function getLocalAccessToken(): string | null {
  return read(ACCESS_KEY, memoryAccessToken)
}

export function getLocalRefreshToken(): string | null {
  return read(REFRESH_KEY, memoryRefreshToken)
}

export function setLocalTokens(tokens: {
  access_token?: string | null
  refresh_token?: string | null
}): void {
  memoryAccessToken = tokens.access_token ?? null
  memoryRefreshToken = tokens.refresh_token ?? null
  write(ACCESS_KEY, memoryAccessToken)
  write(REFRESH_KEY, memoryRefreshToken)
}

export function clearLocalTokens(): void {
  setLocalTokens({ access_token: null, refresh_token: null })
}
