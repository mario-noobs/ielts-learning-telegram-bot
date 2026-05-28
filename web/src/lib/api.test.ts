import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./firebase', () => ({
  auth: { currentUser: null },
}))

import { apiFetch } from './api'
import { clearLocalTokens, setLocalTokens } from './localAuth'

describe('apiFetch', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    clearLocalTokens()
    vi.unstubAllGlobals()
  })

  it('returns undefined for 204 responses', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(null, { status: 204 }),
    )

    await expect(apiFetch('/api/v1/no-content')).resolves.toBeUndefined()
  })

  it('parses JSON responses', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await expect(apiFetch<{ ok: boolean }>('/api/v1/ok')).resolves.toEqual({ ok: true })
  })

  it('sends the local access token when Firebase is not signed in', async () => {
    setLocalTokens({ access_token: 'local-access', refresh_token: 'local-refresh' })
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await apiFetch('/api/v1/me')

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/me',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer local-access',
        }),
      }),
    )
  })

  it('refreshes an expired local token and retries once', async () => {
    setLocalTokens({ access_token: 'old-access', refresh_token: 'old-refresh' })
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: 'common.unauthorized', params: {}, http_status: 401 } }),
          { status: 401 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ access_token: 'new-access', refresh_token: 'new-refresh' }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      )

    await expect(apiFetch<{ ok: boolean }>('/api/v1/me')).resolves.toEqual({ ok: true })

    expect(fetch).toHaveBeenNthCalledWith(
      2,
      '/api/v1/auth/local/refresh',
      expect.objectContaining({
        body: JSON.stringify({ refresh_token: 'old-refresh' }),
      }),
    )
    expect(fetch).toHaveBeenNthCalledWith(
      3,
      '/api/v1/me',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer new-access',
        }),
      }),
    )
  })
})
