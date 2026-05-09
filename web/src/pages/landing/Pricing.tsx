import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '../../components/ui'
import Icon from '../../components/Icon'
import { track } from '../../lib/analytics'
import {
  MARKETING_TO_DB_PLAN,
  MarketingTier,
  PLAN_QUOTA,
} from '../../lib/plans'

interface TierCard {
  tier: MarketingTier
  highlighted: boolean
  // Per-plan extras the i18n bundle doesn't carry (counts come from PLAN_QUOTA).
  extra: { speakingCoach?: boolean; mockExams?: boolean; coachReview?: boolean }
}

const TIERS: TierCard[] = [
  { tier: 'free', highlighted: false, extra: {} },
  { tier: 'pro', highlighted: true, extra: {} },
  { tier: 'team', highlighted: false, extra: {} },
  { tier: 'org', highlighted: false, extra: { coachReview: true } },
]

export default function Pricing() {
  const { t } = useTranslation('landing')
  const navigate = useNavigate()
  const [yearly, setYearly] = useState(true)

  const handleChoose = (tier: MarketingTier) => {
    const planId = MARKETING_TO_DB_PLAN[tier]
    track('landing_pricing_cta', { plan: planId, yearly })
    try {
      localStorage.setItem('intended_plan', planId)
    } catch {
      /* private mode / quota — query param still carries intent */
    }
    navigate(`/login?plan=${planId}`)
  }

  return (
    <section
      id="pricing"
      className="bg-surface px-4 py-16 sm:px-6 sm:py-24"
      aria-labelledby="pricing-heading"
    >
      <div className="mx-auto max-w-7xl">
        <h2
          id="pricing-heading"
          className="mb-4 text-center text-3xl font-bold text-fg sm:text-4xl"
        >
          {t('pricing.heading')}
        </h2>
        <p className="mb-8 text-center text-base text-muted-fg sm:text-lg">
          {t('pricing.subheading')}
        </p>

        <div className="mb-12 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setYearly(false)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              !yearly
                ? 'bg-primary text-on-primary font-semibold'
                : 'text-muted-fg hover:text-fg'
            }`}
            aria-pressed={!yearly}
          >
            {t('pricing.monthly')}
          </button>
          <button
            type="button"
            onClick={() => setYearly(true)}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors ${
              yearly
                ? 'bg-primary text-on-primary font-semibold'
                : 'text-muted-fg hover:text-fg'
            }`}
            aria-pressed={yearly}
          >
            {t('pricing.yearly')}
            <Badge variant="primary">{t('pricing.yearlySavings')}</Badge>
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4 md:items-stretch">
          {TIERS.map((tc) => {
            const quota = PLAN_QUOTA[tc.tier]
            const tName = t(`pricing.tiers.${tc.tier}.name`)
            const tTagline = t(`pricing.tiers.${tc.tier}.tagline`)
            const tCta = t(`pricing.tiers.${tc.tier}.cta`)
            const tPriceMonthly = t(`pricing.tiers.${tc.tier}.priceMonthly`)
            const tPriceYearly = t(`pricing.tiers.${tc.tier}.priceYearly`)
            const tCadence = yearly
              ? t('pricing.cadenceYearly')
              : t('pricing.cadenceMonthly')

            // US-#221: lead with the model-quality differentiator —
            // "premium AI grader" is the headline value of upgrading.
            // Free advertises "fast" (Llama 3.1 8B is genuinely faster
            // than 70B); paid tiers advertise "premium" + per-seat
            // variant for Team/Org.
            const modelLineKey =
              tc.tier === 'free'
                ? 'pricing.features.modelFast'
                : (tc.tier === 'team' || tc.tier === 'org')
                  ? 'pricing.features.modelPremiumSeats'
                  : 'pricing.features.modelPremium'
            const features: string[] = [
              t(modelLineKey),
              t('pricing.features.dailyCalls', { n: quota.daily }),
              t('pricing.features.monthlyCalls', { n: quota.monthly }),
            ]
            if (quota.maxSeats) {
              features.push(
                t('pricing.features.maxSeats', { n: quota.maxSeats }),
              )
            }
            if (tc.extra.coachReview) {
              features.push(t('pricing.features.coachReview'))
            }

            const card = (
              <Card className="flex h-full flex-col" aria-label={tName}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xl">{tName}</CardTitle>
                    {tc.highlighted && (
                      <Badge variant="primary">{t('pricing.popular')}</Badge>
                    )}
                  </div>
                  <CardDescription>{tTagline}</CardDescription>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-fg">
                      {yearly ? tPriceYearly : tPriceMonthly}
                    </span>
                    {tCadence && (
                      <span className="text-sm text-muted-fg">{tCadence}</span>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="flex-1">
                  <ul className="flex min-h-[140px] flex-col gap-3">
                    {features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm">
                        <Icon
                          name="Check"
                          size="sm"
                          variant="primary"
                          className="mt-0.5"
                        />
                        <span className="text-fg">{f}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter>
                  <Button
                    variant={tc.highlighted ? 'primary' : 'secondary'}
                    size="lg"
                    className="w-full"
                    onClick={() => handleChoose(tc.tier)}
                  >
                    {tCta}
                  </Button>
                </CardFooter>
              </Card>
            )

            return tc.highlighted ? (
              <div
                key={tc.tier}
                className="rounded-2xl ring-2 ring-primary md:scale-[1.02] md:shadow-lg md:transition-transform"
              >
                {card}
              </div>
            ) : (
              <div key={tc.tier}>{card}</div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
