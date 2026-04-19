import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { track } from '../../lib/analytics'

interface Props {
  /** Field the settings page should scroll / focus on open */
  focusField: 'target-band' | 'exam-date'
}

export default function PersonalizationCTA({ focusField }: Props) {
  const { t } = useTranslation('dashboard')
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  const isBand = focusField === 'target-band'
  const key = isBand ? 'targetBand' : 'examDate'

  return (
    <section
      aria-labelledby="personalization-cta-heading"
      className="rounded-2xl border border-primary/20 bg-primary/5 p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h2
            id="personalization-cta-heading"
            className="font-semibold text-fg"
          >
            {t('personalization.heading')}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-fg">
            {t(`personalization.${key}.message`)}
          </p>
          <Link
            to={`/settings#${focusField}`}
            onClick={() => track('dashboard_personalization_cta_click', { field: focusField })}
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-fg transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Icon name="Plus" size="sm" />
            {t(`personalization.${key}.cta`)}
          </Link>
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label={t('personalization.dismiss')}
          className="rounded-lg p-1.5 text-muted-fg transition-colors hover:bg-surface hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="X" size="sm" />
        </button>
      </div>
    </section>
  )
}
