import { apiFetch } from './api'
import { parseApiError } from './apiError'
import { auth } from './firebase'

const API_URL = import.meta.env.VITE_API_URL || ''

/** Subcollection-merge counts echoed by `POST /api/v1/link/redeem` for sub-case B. */
export interface LinkRedeemMergeCounts {
  vocab_merged: number
  vocab_dropped: number
  quiz_merged: number
  writing_merged: number
  daily_merged: number
  daily_skipped: number
}

export interface LinkRedeemProfile {
  id: string
  name: string
  email?: string | null
  target_band: number
  topics: string[]
  total_words?: number
  total_quizzes?: number
}

export interface LinkRedeemResponse {
  status: 'linked' | 'merged' | 'already_linked'
  profile: LinkRedeemProfile
  counts: LinkRedeemMergeCounts | null
}

export interface LinkStartResponse {
  token: string
  bot_deep_link: string
  expires_at: string
}

/** Mint a `web_to_tg` token + bot deep-link (US-M12.2). */
export function startLink(): Promise<LinkStartResponse> {
  return apiFetch<LinkStartResponse>('/api/v1/link/start', { method: 'POST' })
}

/** Redeem a `tg_to_web` token from the web side (US-M12.2). */
export function redeemLink(token: string): Promise<LinkRedeemResponse> {
  return apiFetch<LinkRedeemResponse>('/api/v1/link/redeem', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

/** Detach the current Firebase Auth identity from its Telegram account
 * (US-M12.1). Returns nothing on success. The DELETE returns 204 with
 * no body, so this bypasses ``apiFetch``'s implicit ``res.json()``. */
export async function unlinkTelegram(): Promise<void> {
  const user = auth.currentUser
  const token = user ? await user.getIdToken() : null
  const res = await fetch(`${API_URL}/api/v1/users/link`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!res.ok) {
    const raw = await res.json().catch(() => null)
    throw parseApiError(raw, res.status)
  }
}
