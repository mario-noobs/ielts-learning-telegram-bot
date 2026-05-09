import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

/**
 * Plan badge — pill displaying the current subscription tier (US-M14.2).
 *
 * Used in two places:
 * 1. AppShell sidebar bottom group (compact rendering — when sidebar
 *    is collapsed, only the chip is shown without the upgrade CTA).
 * 2. /settings Plan tab header (full rendering with upgrade CTA for
 *    free users).
 *
 * Tier mapping (matches `web/src/lib/plans.ts::MARKETING_TO_DB_PLAN`):
 *   free          → muted neutral chip + Upgrade CTA
 *   personal_pro  → primary teal solid pill labelled "PRO"
 *   team_member   → accent solid pill labelled "TEAM"
 *   org_member    → success solid pill labelled "ORG"
 */

interface Props {
  plan: string
  /** Sidebar-collapsed state — when true, hide CTA + label, show only
   *  a small letter chip so the badge fits the icon-only rail. */
  compact?: boolean
  /** Hide the Upgrade CTA next to the Free chip. */
  hideUpgrade?: boolean
  className?: string
}

interface TierStyle {
  label: string
  letter: string
  cls: string
}

function tierStyle(plan: string, t: (k: string) => string): TierStyle {
  switch (plan) {
    case 'personal_pro':
      return {
        label: t('plan.badge.pro'),
        letter: 'P',
        cls: 'bg-primary text-on-primary',
      }
    case 'team_member':
      return {
        label: t('plan.badge.team'),
        letter: 'T',
        cls: 'bg-accent text-on-accent',
      }
    case 'org_member':
      return {
        label: t('plan.badge.org'),
        letter: 'O',
        cls: 'bg-success text-on-success',
      }
    default:
      return {
        label: t('plan.badge.free'),
        letter: 'F',
        cls: 'border border-border bg-surface text-muted-fg',
      }
  }
}

export default function PlanBadge({
  plan,
  compact = false,
  hideUpgrade = false,
  className = '',
}: Props) {
  const { t } = useTranslation('common')
  const style = tierStyle(plan, t)
  const isFree = plan === 'free' || !plan

  if (compact) {
    return (
      <span
        aria-label={style.label}
        className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${style.cls} ${className}`}
      >
        {style.letter}
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-2 ${className}`}
    >
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide ${style.cls}`}
      >
        {style.label}
      </span>
      {isFree && !hideUpgrade && (
        <Link
          to="/pricing"
          className="text-xs font-medium text-primary hover:underline"
        >
          {t('plan.badge.upgrade')}
        </Link>
      )}
    </span>
  )
}
