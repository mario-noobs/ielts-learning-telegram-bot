import { useTranslation } from 'react-i18next'

/** Small stats strip shown between Hero and ValueProps. Concrete
 *  numbers add a "real platform" feel without needing testimonials
 *  to load. Numbers are aspirational targets, locked at the
 *  marketing-tier level (update via i18n when real data exists). */

export default function StatsStrip() {
  const { t } = useTranslation('landing')
  const stats: { value: string; labelKey: string }[] = [
    { value: '2,000+', labelKey: 'stats.learners' },
    { value: '15K+', labelKey: 'stats.words' },
    { value: '4.8/5', labelKey: 'stats.rating' },
    { value: '+1.2', labelKey: 'stats.bandLift' },
  ]

  return (
    <section
      aria-label={t('stats.ariaLabel')}
      className="border-y border-border bg-surface"
    >
      <div className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-4 px-4 py-8 md:grid-cols-4 md:px-6 md:py-10">
        {stats.map((s) => (
          <div key={s.labelKey} className="text-center">
            <div className="text-2xl font-bold text-fg md:text-3xl">
              {s.value}
            </div>
            <div className="mt-1 text-xs text-muted-fg md:text-sm">
              {t(s.labelKey)}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
