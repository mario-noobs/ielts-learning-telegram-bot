import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Icon from './Icon'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'

/**
 * Modal for setting the user's exam date inline from the dashboard.
 *
 * Replaces both the inline-form variant of <ReadinessTrack> empty state
 * and the navigate-to-/settings flow used by <PersonalizationCTA>. The
 * surface is the dashboard, so a popup keeps the user in context — no
 * mid-flow page change.
 */
interface Props {
  open: boolean
  onClose: () => void
  /**
   * Called after a successful PATCH /me. Parent should re-fetch
   * whatever data depends on `exam_date` (readiness, profile, etc.)
   * before re-rendering. Returns void or Promise<void>.
   */
  onSaved: () => void | Promise<void>
}

export default function ExamDateDialog({ open, onClose, onSaved }: Props) {
  const { t } = useTranslation('dashboard')
  const [date, setDate] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dateInputRef = useRef<HTMLInputElement | null>(null)

  // Esc closes; focus the date input on open. Reset state every time
  // the dialog (re-)opens so a previous error doesn't bleed into the
  // next attempt.
  useEffect(() => {
    if (!open) return
    setDate('')
    setError(null)
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    // Defer focus to next tick so the input is in the DOM.
    const id = window.setTimeout(() => dateInputRef.current?.focus(), 0)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      window.clearTimeout(id)
    }
  }, [open, onClose])

  if (!open) return null

  // min=today; an exam date in the past is meaningless for readiness.
  const today = new Date().toISOString().slice(0, 10)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!date || saving) return
    setSaving(true)
    setError(null)
    try {
      await apiFetch('/api/v1/me', {
        method: 'PATCH',
        body: JSON.stringify({ exam_date: date }),
      })
      await onSaved()
      onClose()
    } catch (err) {
      setError(localizeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="exam-date-dialog-title"
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={(e) => {
        // Backdrop click closes; clicks inside the panel don't bubble.
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="w-full max-w-sm rounded-2xl bg-surface-raised p-5 shadow-lg">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Icon name="Calendar" size="md" variant="primary" />
            </span>
            <h3
              id="exam-date-dialog-title"
              className="text-base font-semibold text-fg"
            >
              {t('examDateDialog.title')}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('examDateDialog.close')}
            className="rounded-lg p-1.5 text-muted-fg transition-colors hover:bg-surface hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon name="X" size="sm" />
          </button>
        </div>

        <p className="mt-2 text-sm text-muted-fg">
          {t('examDateDialog.description')}
        </p>

        <form onSubmit={submit} className="mt-4">
          <label
            htmlFor="exam-date-dialog-input"
            className="text-sm font-semibold text-fg"
          >
            {t('examDateDialog.label')}
          </label>
          <input
            ref={dateInputRef}
            id="exam-date-dialog-input"
            type="date"
            min={today}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-fg focus:border-primary focus:outline-none"
          />
          {error ? (
            <p role="alert" className="mt-2 text-sm text-danger">
              {error}
            </p>
          ) : null}
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="inline-flex items-center justify-center rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-fg hover:bg-surface-raised disabled:opacity-50"
            >
              {t('examDateDialog.cancel')}
            </button>
            <button
              type="submit"
              disabled={!date || saving}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-fg hover:bg-primary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {saving
                ? t('examDateDialog.saving')
                : t('examDateDialog.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
