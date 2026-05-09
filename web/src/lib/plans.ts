/**
 * Marketing-tier ↔ DB-plan mapping (US-#211).
 *
 * The Pricing page renders marketing-friendly tier names ("Pro",
 * "Team", etc.); the backend `plans` table seeds canonical IDs
 * (`free`, `personal_pro`, `team_member`, `org_member` per
 * `migrations/versions/0002_admin_baseline.py`). When the user clicks
 * "Get Pro", we MUST send the DB id to the API — never round-trip the
 * marketing alias.
 *
 * Numbers below mirror the DB seed exactly. If the seed quotas change
 * (admin UI override, new migration), update here too.
 */

export type MarketingTier = 'free' | 'pro' | 'team' | 'org'
export type PlanId = 'free' | 'personal_pro' | 'team_member' | 'org_member'

export const MARKETING_TO_DB_PLAN: Record<MarketingTier, PlanId> = {
  free: 'free',
  pro: 'personal_pro',
  team: 'team_member',
  org: 'org_member',
}

export interface PlanQuota {
  daily: number
  monthly: number
  maxSeats: number | null
}

export const PLAN_QUOTA: Record<MarketingTier, PlanQuota> = {
  free: { daily: 10, monthly: 200, maxSeats: null },
  pro: { daily: 200, monthly: 5000, maxSeats: null },
  team: { daily: 200, monthly: 5000, maxSeats: 25 },
  org: { daily: 500, monthly: 12000, maxSeats: 200 },
}
