import { useEffect, useState } from 'react'
import { apiFetch } from './api'

export interface FeaturePoint {
  feature: string
  count: number
}

export interface MeAiUsage {
  plan: string
  quota_daily: number
  used_today: number
  by_feature: FeaturePoint[]
  reset_at: string
}

export interface UseMyAiUsage {
  data: MeAiUsage | null
  error: Error | null
  loading: boolean
}

/**
 * Shared fetch hook for `GET /api/v1/me/ai-usage` (US-M13.x).
 *
 * Used by both the Dashboard widget (US-M13.1) and the threshold-aware
 * `<UpgradeBanner>` (US-M13.3). Data is read-only — the endpoint never
 * increments usage.
 */
export function useMyAiUsage(): UseMyAiUsage {
  const [data, setData] = useState<MeAiUsage | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    apiFetch<MeAiUsage>('/api/v1/me/ai-usage')
      .then((d) => {
        if (cancelled) return
        setData(d)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e instanceof Error ? e : new Error('ai-usage fetch failed'))
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { data, error, loading }
}
