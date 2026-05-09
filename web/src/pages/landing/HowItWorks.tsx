/**
 * "How it works" 3-step section (US-#223).
 *
 * Inspired by HelloInterview's marketing landing — three numbered cards
 * each with a wireframe screenshot of the actual product surface, so
 * a visitor sees the journey before clicking through.
 *
 * IELTS journey: set goal → daily plan + AI feedback → track readiness
 * → take the exam. Each illustration lives in `web/public/landing/` —
 * v1 inline-traced wireframe SVGs; designer iterates to AI-generated
 * (Midjourney/Ideogram) variants without touching this component.
 */

import { useTranslation } from 'react-i18next'

interface StepDef {
  num: 1 | 2 | 3
  illustration: string
  i18nKey: 'goal' | 'feedback' | 'readiness'
}

const STEPS: StepDef[] = [
  { num: 1, illustration: '/landing/howitworks-1-goal.svg', i18nKey: 'goal' },
  { num: 2, illustration: '/landing/howitworks-2-feedback.svg', i18nKey: 'feedback' },
  { num: 3, illustration: '/landing/howitworks-3-readiness.svg', i18nKey: 'readiness' },
]

export default function HowItWorks() {
  const { t } = useTranslation('landing')
  return (
    <section
      aria-labelledby="howitworks-heading"
      className="mx-auto w-full max-w-6xl px-4 py-12 md:px-6 md:py-20"
    >
      <div className="mb-10 max-w-2xl md:mb-14">
        <h2
          id="howitworks-heading"
          className="text-2xl font-bold text-fg md:text-4xl"
        >
          {t('howItWorks.heading')}
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-fg md:text-lg">
          {t('howItWorks.subheading')}
        </p>
      </div>
      <ol className="grid gap-6 md:grid-cols-3 md:gap-8">
        {STEPS.map((s) => (
          <li
            key={s.num}
            className="group relative overflow-hidden rounded-2xl border border-border bg-surface-raised transition-shadow hover:shadow-lg"
          >
            {/* Wireframe illustration up top — matches each step's
                actual UI so the visitor recognises the surface when
                they sign up. */}
            <div className="relative aspect-[400/260] w-full bg-gradient-to-br from-primary/10 to-primary/5">
              <img
                src={s.illustration}
                alt=""
                aria-hidden="true"
                loading="lazy"
                className="h-full w-full object-cover"
              />
              <span
                aria-hidden="true"
                className="absolute left-4 top-4 flex h-10 w-10 items-center justify-center rounded-xl bg-fg text-base font-bold text-bg shadow-md"
              >
                {s.num}
              </span>
            </div>
            <div className="p-5">
              <h3 className="text-lg font-semibold text-primary">
                {t(`howItWorks.steps.${s.i18nKey}.title`)}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-fg">
                {t(`howItWorks.steps.${s.i18nKey}.body`)}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
