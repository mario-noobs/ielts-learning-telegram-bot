import { useTranslation } from 'react-i18next'

/**
 * Optional secondary CTA that opens the IELTS Telegram community group.
 *
 * CTA-only by design (US-M12.3): the bot doesn't auto-add anyone — the
 * user clicks through and Telegram handles membership. If
 * `VITE_TELEGRAM_GROUP_INVITE_URL` is unset, the component renders
 * nothing so the surrounding layout collapses cleanly.
 */
export default function GroupJoinCTA() {
  const { t } = useTranslation('link')
  const url = import.meta.env.VITE_TELEGRAM_GROUP_INVITE_URL
  if (!url) return null

  return (
    <div className="rounded-xl border border-border/60 bg-surface-raised p-4">
      <p className="text-sm text-fg font-medium">{t('group.title')}</p>
      <p className="text-xs text-muted-fg mt-1">{t('group.subtitle')}</p>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 mt-3 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        {t('group.cta')}
      </a>
    </div>
  )
}
