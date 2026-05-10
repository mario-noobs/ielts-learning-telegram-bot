import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import ExamDateDialog from '../../components/ExamDateDialog'
import Icon from '../../components/Icon'
import { track } from '../../lib/analytics'

interface Props {
  /** Field the settings page should scroll / focus on open */
  focusField: 'target-band' | 'exam-date'
  /** Re-fetch profile after a successful exam-date save (only used for the
   *  exam-date variant). Optional so target-band path stays unchanged. */
  onSaved?: () => void | Promise<void>
}

export default function PersonalizationCTA({ focusField, onSaved }: Props) {
  const { t } = useTranslation('dashboard')
  const [dismissed, setDismissed] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  if (dismissed) return null

  const isBand = focusField === 'target-band'
  const key = isBand ? 'targetBand' : 'examDate'

  // exam-date opens an inline dialog so the user stays on the
  // dashboard. target-band still routes to /settings — no inline
  // editor is justified for that field yet.
  const ctaContent = (
    <>
      <Icon name="Plus" size="sm" />
      {t(`personalization.${key}.cta`)}
    </>
  )
  const ctaClass =
    'mt-3 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-fg transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'

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
          {isBand ? (
            <Link
              to="/settings#target-band"
              onClick={() => track('dashboard_personalization_cta_click', { field: focusField })}
              className={ctaClass}
            >
              {ctaContent}
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => {
                track('dashboard_personalization_cta_click', { field: focusField })
                setDialogOpen(true)
              }}
              className={ctaClass}
            >
              {ctaContent}
            </button>
          )}
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
      {!isBand && (
        <ExamDateDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onSaved={async () => {
            if (onSaved) await onSaved()
          }}
        />
      )}
    </section>
  )
}
