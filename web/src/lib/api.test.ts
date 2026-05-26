import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./firebase', () => ({
  auth: { currentUser: null },
}))

import { apiFetch } from './api'

describe('apiFetch', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
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
})
